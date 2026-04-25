"""
Integration Testing Guide for MNVPN VPN Service

This guide provides step-by-step testing instructions for the complete user flow.
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Test 1: Database functionality
async def test_database():
    print("=" * 60)
    print("TEST 1: Database Initialization and Operations")
    print("=" * 60)
    
    from database import (
        init_db, add_user, get_user, update_user_subscription,
        add_payment, get_payment
    )
    
    try:
        # Initialize database
        await init_db()
        print("✓ Database initialized successfully\n")
        
        # Add test user
        test_user_id = 987654321
        test_username = "test_user"
        await add_user(test_user_id, test_username)
        print(f"✓ Test user created: {test_username} (ID: {test_user_id})\n")
        
        # Retrieve user
        user = await get_user(test_user_id)
        if user:
            print(f"✓ User retrieved from database:")
            print(f"  - ID: {user['user_id']}")
            print(f"  - Username: {user['username']}")
            print(f"  - Subscription: {user['subscription_expiry']}\n")
        
        # Update subscription
        new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
        await update_user_subscription(test_user_id, new_expiry)
        print(f"✓ Subscription updated to: {new_expiry}\n")
        
        # Create payment record
        import time
        payment_id = f"test_payment_{int(time.time())}"
        await add_payment(
            payment_id=payment_id,
            user_id=test_user_id,
            amount_rubles=100.0,
            payment_type="subscription",
            provider="test",
            description="Test payment"
        )
        print(f"✓ Payment record created: {payment_id}\n")
        
        # Retrieve payment
        payment = await get_payment(payment_id)
        if payment:
            print(f"✓ Payment retrieved from database")
            print(f"  - Amount: {payment['amount_rubles']}₽")
            print(f"  - Status: {payment['status']}\n")
        
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}\n")
        return False


# Test 2: VPN Service connectivity
async def test_vpn_service():
    print("=" * 60)
    print("TEST 2: VPN Service (3X-UI) Connectivity")
    print("=" * 60)
    
    from vpn_service import vpn_service
    
    try:
        # Login to 3X-UI
        connected = await vpn_service.login_3xui()
        if connected:
            print("✓ Successfully connected to 3X-UI panel\n")
        else:
            print("✗ Failed to connect to 3X-UI panel")
            print("  Make sure VPN_PANEL_URL and credentials are correct in .env\n")
            return False
        
        # Test client creation
        test_user_id = 987654321
        test_username = "test_user"
        
        print("Creating test VPN client...")
        client_result = await vpn_service.add_or_update_client(
            user_id=test_user_id,
            username=test_username,
            limit_ip=1
        )
        
        if client_result:
            print(f"✓ VPN client created successfully")
            print(f"  - UUID: {client_result['uuid']}")
            print(f"  - Sub ID: {client_result['sub_id']}\n")
        else:
            print("✗ Failed to create VPN client\n")
            return False
        
        # Test subscription link generation
        sub_link = vpn_service.generate_subscription_link(
            client_result['sub_id'],
            f"test_user_device"
        )
        print(f"✓ Subscription link generated:")
        print(f"  {sub_link}\n")
        
        return True
    except Exception as e:
        print(f"✗ VPN Service test failed: {e}\n")
        return False


# Test 3: Payment Service
async def test_payment_service():
    print("=" * 60)
    print("TEST 3: Payment Service (Yandex.Kassa)")
    print("=" * 60)
    
    from payment_service import get_payment_service
    
    service = get_payment_service()
    if not service:
        print("⚠ Payment service not initialized")
        print("  Set YANDEX_KASSA_SHOP_ID, API_KEY, WEBHOOK_SECRET in .env\n")
        return False
    
    try:
        test_user_id = 987654321
        
        # Create test invoice
        print("Creating test invoice...")
        invoice = await service.create_invoice(
            user_id=test_user_id,
            amount=100.0,
            description="Test subscription payment",
            metadata={"type": "subscription"}
        )
        
        if invoice:
            print(f"✓ Invoice created successfully")
            print(f"  - Invoice ID: {invoice['id']}")
            print(f"  - Payment link: {invoice['confirmation_url']}")
            print(f"  - Status: {invoice['status']}\n")
            return True
        else:
            print("✗ Failed to create invoice")
            print("  Check Yandex.Kassa credentials\n")
            return False
    except Exception as e:
        print(f"✗ Payment Service test failed: {e}\n")
        return False


# Test 4: Webhook signature verification
async def test_webhook_signature():
    print("=" * 60)
    print("TEST 4: Webhook Signature Verification")
    print("=" * 60)
    
    from payment_service import get_payment_service
    import json
    import hashlib
    
    service = get_payment_service()
    if not service:
        print("⚠ Payment service not initialized\n")
        return False
    
    try:
        # Create test webhook body
        webhook_body = json.dumps({
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_123",
                "status": "succeeded",
                "metadata": {
                    "user_id": "987654321",
                    "type": "subscription"
                }
            }
        }).encode()
        
        # Generate valid signature
        valid_signature = hashlib.sha256(
            webhook_body + service.webhook_secret.encode()
        ).hexdigest()
        
        # Test signature verification
        verified = service.verify_webhook_signature(webhook_body, valid_signature)
        
        if verified:
            print("✓ Valid signature verified successfully\n")
        else:
            print("✗ Valid signature verification failed\n")
            return False
        
        # Test invalid signature
        invalid_signature = "invalid_signature_hash"
        verified = service.verify_webhook_signature(webhook_body, invalid_signature)
        
        if not verified:
            print("✓ Invalid signature correctly rejected\n")
            return True
        else:
            print("✗ Invalid signature not detected\n")
            return False
    
    except Exception as e:
        print(f"✗ Webhook test failed: {e}\n")
        return False


# Test 5: Full user flow simulation
async def test_complete_flow():
    print("=" * 60)
    print("TEST 5: Complete User Flow Simulation")
    print("=" * 60)
    
    from database import (
        add_user, get_user, update_user_subscription,
        get_user_devices, add_device
    )
    from vpn_service import vpn_service
    from payment_service import get_payment_service
    from datetime import datetime, timedelta
    
    test_user_id = 987654322
    test_username = "flow_test_user"
    
    try:
        print("Step 1: Register user")
        await add_user(test_user_id, test_username)
        user = await get_user(test_user_id)
        print(f"✓ User registered: {test_username}\n")
        
        print("Step 2: Create payment invoice")
        payment_service = get_payment_service()
        if payment_service:
            invoice = await payment_service.create_invoice(
                user_id=test_user_id,
                amount=100.0,
                description="Test subscription",
                metadata={"type": "subscription"}
            )
            print(f"✓ Invoice created: {invoice['id']}\n")
        
        print("Step 3: Activate subscription (simulating payment)")
        new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
        await update_user_subscription(test_user_id, new_expiry)
        user = await get_user(test_user_id)
        print(f"✓ Subscription activated until: {user['subscription_expiry']}\n")
        
        print("Step 4: Register VPN device")
        device_info = await vpn_service.register_device(
            user_id=test_user_id,
            username=test_username,
            device_name="Test Device"
        )
        if device_info:
            print(f"✓ Device registered: {device_info['device_name']}")
            print(f"  - UUID: {device_info['uuid'][:8]}...")
            print(f"  - Link: {device_info['subscription_link'][:50]}...\n")
        
        print("Step 5: Verify user devices")
        devices = await get_user_devices(test_user_id)
        print(f"✓ Found {len(devices)} device(s) for user\n")
        
        print("=" * 60)
        print("✓ Complete flow test PASSED")
        print("=" * 60 + "\n")
        return True
    
    except Exception as e:
        print(f"✗ Complete flow test failed: {e}\n")
        return False


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("MNVPN INTEGRATION TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Database", await test_database()))
    results.append(("VPN Service", await test_vpn_service()))
    results.append(("Payment Service", await test_payment_service()))
    results.append(("Webhook Signature", await test_webhook_signature()))
    results.append(("Complete Flow", await test_complete_flow()))
    
    # Print summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    from vpn_service import vpn_service
    await vpn_service.close()
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
