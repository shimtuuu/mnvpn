"""
FastAPI webhook server for handling Yandex.Kassa payment notifications.

This server receives webhook calls from Yandex.Kassa when payment status changes
and updates the database and sends notifications to users via Telegram.
"""

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
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


@app.get("/r")
async def happ_redirect(request: Request):
    """
    MNVPN deep link redirector for Happ VPN client.
    
    Usage: /r?url=happ://add/<subscription_url>#MNVPN
    When user clicks this link:
    - If Happ is installed → opens Happ and adds the subscription
    - If Happ is not installed → shows a branded page with download links
    """
    url = request.query_params.get("url")
    if not url:
        return JSONResponse({"error": "Missing 'url' parameter"}, status_code=400)
    
    # Return an HTML page that tries to open the deep link,
    # with a fallback for users who don't have Happ installed
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MNVPN — Подключение</title>
        <meta http-equiv="refresh" content="0;url={url}">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
                color: #fff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 20px;
            }}
            .card {{
                background: rgba(255,255,255,0.08);
                backdrop-filter: blur(20px);
                border-radius: 24px;
                padding: 40px 30px;
                max-width: 400px;
                width: 100%;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .logo {{ font-size: 48px; margin-bottom: 16px; }}
            h1 {{ font-size: 24px; margin-bottom: 8px; }}
            p {{ color: rgba(255,255,255,0.7); margin-bottom: 24px; font-size: 15px; }}
            .btn {{
                display: inline-block;
                padding: 14px 32px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: #fff;
                text-decoration: none;
                border-radius: 14px;
                font-size: 16px;
                font-weight: 600;
                margin: 6px;
                transition: transform 0.2s;
            }}
            .btn:hover {{ transform: scale(1.05); }}
            .btn-secondary {{
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
            }}
            .spinner {{
                width: 40px; height: 40px;
                border: 3px solid rgba(255,255,255,0.2);
                border-top-color: #667eea;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="spinner"></div>
            <div class="logo">🔐</div>
            <h1>MNVPN</h1>
            <p>Открываем приложение Happ...</p>
            <a href="{url}" class="btn">Открыть в Happ</a><br>
            <a href="https://apps.apple.com/app/id6504518402" class="btn btn-secondary">📱 Скачать Happ (iOS)</a>
            <a href="https://play.google.com/store/apps/details?id=com.happ.vpn" class="btn btn-secondary">🤖 Скачать Happ (Android)</a>
        </div>
        <script>
            // Try to open the deep link
            window.location.href = "{url}";
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/webhook/test")
async def test_webhook(request: Request):
    """Test endpoint to verify webhook connectivity."""
    body = await request.body()
    logger.info(f"Test webhook received: {body}")
    return {"status": "ok", "received": len(body)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
