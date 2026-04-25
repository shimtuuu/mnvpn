"""
Yandex.Kassa payment integration for MNVPN service.
Supports webhook handling for subscription activation and renewals.
"""

import logging
import hmac
import hashlib
import json
import uuid
from typing import Optional, Dict
from datetime import datetime, timedelta
import aiohttp

from config import YANDEX_KASSA_SHOP_ID, YANDEX_KASSA_API_KEY, YANDEX_KASSA_WEBHOOK_SECRET
from database import (
    add_payment, update_payment_status, get_payment, get_user,
    update_user_subscription, update_user_device_limit,
    record_subscription_history
)

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Yandex.Kassa payment gateway integration.
    
    Supports:
    - Creating payment invoices for subscriptions
    - Processing webhook notifications
    - Idempotent payment verification
    """
    
    def __init__(self, shop_id: str, api_key: str, webhook_secret: str):
        self.shop_id = shop_id
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = "https://api.yookassa.ru/v3"
    
    async def create_invoice(self, user_id: int, amount: float, 
                           description: str, metadata: Dict = None) -> Optional[Dict]:
        """
        Create a Yandex.Kassa invoice.
        
        Args:
            user_id: Telegram user ID
            amount: Amount in rubles (must be >= 10)
            description: Invoice description for user
            metadata: Custom metadata dict
            
        Returns:
            Dictionary with 'id', 'confirmation_url', 'payment_id' or None on error
        """
        if amount < 10:
            logger.error(f"Invalid amount {amount}: minimum is 10₽")
            return None
        
        payment_id = str(uuid.uuid4())
        
        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "payment_id": payment_id,
                **(metadata or {})
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://example.com/payment-success"  # Change to your domain
            },
            "capture": True
        }
        
        # Create payment record before sending to Kassa
        try:
            payment_type = metadata.get("type", "subscription") if metadata else "subscription"
            await add_payment(
                payment_id=payment_id,
                user_id=user_id,
                amount_rubles=amount,
                payment_type=payment_type,
                provider="yandex_kassa",
                description=description
            )
        except Exception as e:
            logger.error(f"Error creating payment record: {e}")
            return None
        
        try:
            auth = aiohttp.BasicAuth(self.shop_id, self.api_key)
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.post(
                    f"{self.base_url}/payments",
                    json=payload,
                    headers={"Idempotence-Key": payment_id}
                ) as resp:
                    if resp.status in [200, 201]:
                        result = await resp.json()
                        logger.info(f"Invoice created: {result.get('id')}")
                        return {
                            "id": result.get("id"),
                            "confirmation_url": result.get("confirmation", {}).get("confirmation_url"),
                            "payment_id": payment_id,
                            "status": result.get("status")
                        }
                    else:
                        error = await resp.text()
                        logger.error(f"Failed to create invoice: {resp.status} - {error}")
                        return None
        except Exception as e:
            logger.error(f"Error creating invoice: {e}")
            return None
    
    def verify_webhook_signature(self, request_body: bytes, signature: str) -> bool:
        """
        Verify Yandex.Kassa webhook signature.
        
        Args:
            request_body: Raw webhook request body
            signature: X-Yandex-Checkout-API-Signature header value
            
        Returns:
            True if signature is valid
        """
        expected_signature = hashlib.sha256(
            request_body + self.webhook_secret.encode()
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, webhook_data: Dict) -> bool:
        """
        Process Yandex.Kassa webhook notification.
        
        Handles successful payments and updates user subscription.
        
        Args:
            webhook_data: Parsed webhook JSON data
            
        Returns:
            True if webhook was processed successfully
        """
        try:
            event_type = webhook_data.get("event")
            payment = webhook_data.get("object", {})
            payment_id = payment.get("id")
            status = payment.get("status")
            
            logger.info(f"Processing webhook: {event_type} for payment {payment_id}")
            
            # Only process successful payments
            if event_type == "payment.succeeded" and status == "succeeded":
                metadata = payment.get("metadata", {})
                internal_payment_id = metadata.get("payment_id")
                user_id = int(metadata.get("user_id"))
                payment_type = metadata.get("type", "subscription")
                
                # Update payment record
                await update_payment_status(
                    payment_id=internal_payment_id,
                    status="completed",
                    external_payment_id=payment_id
                )
                
                user = await get_user(user_id)
                if not user:
                    logger.error(f"User {user_id} not found for payment {payment_id}")
                    return False
                
                # Activate subscription
                if payment_type == "subscription":
                    old_expiry = user[2]
                    new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
                    await update_user_subscription(user_id, new_expiry)
                    await record_subscription_history(
                        user_id=user_id,
                        action="subscription_purchased",
                        old_expiry=old_expiry,
                        new_expiry=new_expiry,
                        payment_id=internal_payment_id
                    )
                    logger.info(f"Subscription activated for user {user_id}")
                
                # Add device/upgrade
                elif payment_type == "device_upgrade":
                    current_limit = user[3]
                    new_limit = current_limit + 1
                    await update_user_device_limit(user_id, new_limit)
                    logger.info(f"Device limit increased to {new_limit} for user {user_id}")
                
                return True
            
            elif event_type == "payment.canceled":
                logger.info(f"Payment {payment_id} was canceled")
                # Update payment status to cancelled
                if "metadata" in payment:
                    internal_payment_id = payment.get("metadata", {}).get("payment_id")
                    await update_payment_status(internal_payment_id, "cancelled")
                return True
            
            else:
                logger.debug(f"Ignoring webhook event: {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False
    
    async def check_payment_status(self, payment_id: str) -> Optional[str]:
        """
        Check payment status in Yandex.Kassa.
        
        Args:
            payment_id: Yandex.Kassa payment ID
            
        Returns:
            Payment status string or None on error
        """
        try:
            auth = aiohttp.BasicAuth(self.shop_id, self.api_key)
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(f"{self.base_url}/payments/{payment_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("status")
                    else:
                        logger.error(f"Failed to check payment status: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return None


# Global payment service instance
payment_service = None


def init_payment_service(shop_id: str, api_key: str, webhook_secret: str):
    """Initialize global payment service instance."""
    global payment_service
    payment_service = PaymentService(shop_id, api_key, webhook_secret)
    logger.info("Payment service initialized")


def get_payment_service() -> Optional[PaymentService]:
    """Get global payment service instance."""
    return payment_service
