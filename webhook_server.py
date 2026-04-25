"""
FastAPI webhook server for handling Yandex.Kassa payment notifications.

This server receives webhook calls from Yandex.Kassa when payment status changes
and updates the database and sends notifications to users via Telegram.
"""

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json
from typing import Optional

from payment_service import get_payment_service
from database import get_user
from bot import bot_instance  # Will be set by main bot

logger = logging.getLogger(__name__)
app = FastAPI(title="MNVPN Payment Webhook")


@app.post("/webhook/payment")
async def handle_payment_webhook(request: Request):
    """
    Handle Yandex.Kassa payment webhook notifications.
    
    Expected request headers:
    - X-Yandex-Checkout-API-Signature: HMAC-SHA256 signature
    
    Expected body:
    {
        "type": "notification",
        "event": "payment.succeeded" | "payment.canceled",
        "object": {...}
    }
    """
    try:
        # Read raw body for signature verification
        body = await request.body()
        
        # Get signature from header
        signature = request.headers.get("X-Yandex-Checkout-API-Signature")
        if not signature:
            logger.warning("Webhook received without signature header")
            return JSONResponse({"status": "error", "message": "Missing signature"}, status_code=400)
        
        # Parse JSON
        webhook_data = json.loads(body)
        logger.info(f"Received webhook: {webhook_data.get('event')}")
        
        # Verify signature
        payment_service = get_payment_service()
        if not payment_service:
            logger.error("Payment service not initialized")
            return JSONResponse({"status": "error"}, status_code=500)
        
        if not payment_service.verify_webhook_signature(body, signature):
            logger.warning("Invalid webhook signature")
            return JSONResponse({"status": "error", "message": "Invalid signature"}, status_code=403)
        
        # Process webhook
        success = await payment_service.process_webhook(webhook_data)
        
        if success:
            # Try to notify user via Telegram
            try:
                payment = webhook_data.get("object", {})
                metadata = payment.get("metadata", {})
                user_id = int(metadata.get("user_id"))
                event_type = webhook_data.get("event")
                
                user = await get_user(user_id)
                if user:
                    if event_type == "payment.succeeded":
                        payment_type = metadata.get("type", "subscription")
                        if payment_type == "subscription":
                            message_text = (
                                "✅ *Оплата успешно принята!*\n\n"
                                "Ваша подписка активирована на 30 дней.\n"
                                "Нажмите 'Получить VPN ключ' для начала использования."
                            )
                        else:
                            message_text = (
                                "✅ *Оплата успешно принята!*\n\n"
                                "Лимит устройств увеличен.\n"
                                "Теперь вы можете использовать больше устройств одновременно."
                            )
                        
                        if bot_instance:
                            try:
                                await bot_instance.send_message(
                                    user_id,
                                    message_text,
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify user {user_id}: {e}")
                    
                    elif event_type == "payment.canceled":
                        if bot_instance:
                            try:
                                await bot_instance.send_message(
                                    user_id,
                                    "❌ Платеж был отменен.\n\nПожалуйста, попробуйте еще раз."
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Error sending notification to user: {e}")
            
            return JSONResponse({"status": "ok", "code": 0})
        else:
            return JSONResponse({"status": "error", "code": 1}, status_code=400)
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)
    
    except Exception as e:
        logger.error(f"Unexpected error handling webhook: {e}")
        return JSONResponse({"status": "error"}, status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/webhook/test")
async def test_webhook(request: Request):
    """Test endpoint to verify webhook connectivity."""
    body = await request.body()
    logger.info(f"Test webhook received: {body}")
    return {"status": "ok", "received": len(body)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
