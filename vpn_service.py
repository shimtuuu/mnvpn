"""
VPN Service — Integration with 3X-UI panel.
Handles client creation, link generation, QR codes, config export.
"""

import asyncio
import logging
import uuid
import aiohttp
import json
import qrcode
from io import BytesIO
from datetime import datetime
from typing import Optional, Dict, List

from config import (
    VPN_PANEL_URL, VPN_PANEL_USERNAME, VPN_PANEL_PASSWORD,
    SERVER_IP, SERVER_DOMAIN, SUB_PORT, SUB_SECRET, INBOUND_ID
)
from database import add_device, get_user_devices, deactivate_device

# Reality Settings (Fetched from panel)
REALITY_PUBLIC_KEY = "Dodq32f0P7YVGHkvdI-njibzKlibaShzqkBrglCDEyA"
REALITY_SNI = "www.microsoft.com"
REALITY_SHORT_ID = "0c539e1b54f35027"

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds between retries


class VPNService:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self._logged_in = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookie_jar=self.cookie_jar,
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=30)  # increased from 10s
            )
            self._logged_in = False
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def login_3xui(self) -> bool:
        """Login to 3X-UI panel and keep session."""
        session = await self._get_session()
        login_url = f"{VPN_PANEL_URL}/login"
        data = {"username": VPN_PANEL_USERNAME, "password": VPN_PANEL_PASSWORD}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.post(login_url, data=data) as resp:
                    if resp.status == 200:
                        json_data = await resp.json()
                        if json_data.get("success"):
                            logger.info("Successfully logged into 3X-UI")
                            self._logged_in = True
                            return True
                    logger.warning(f"Login attempt {attempt}/{MAX_RETRIES} failed: {resp.status}")
            except Exception as e:
                logger.warning(f"Login attempt {attempt}/{MAX_RETRIES} error: {e}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

        logger.error("All login attempts to 3X-UI failed")
        self._logged_in = False
        return False

    async def _ensure_logged_in(self):
        """Ensure we have an active authenticated session, re-login if needed."""
        if self.session is None or self.session.closed:
            self._logged_in = False

        if not self._logged_in:
            await self.login_3xui()

    async def get_inbounds(self) -> List[dict]:
        """Fetch all inbounds from 3X-UI with retry logic."""
        for attempt in range(1, MAX_RETRIES + 1):
            await self._ensure_logged_in()
            session = await self._get_session()
            try:
                url = f"{VPN_PANEL_URL}/panel/api/inbounds/list"
                async with session.get(url) as resp:
                    if resp.status == 401:
                        # Session expired — force re-login on next attempt
                        logger.warning(f"get_inbounds attempt {attempt}: session expired, re-logging in...")
                        self._logged_in = False
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            inbounds = data.get("obj", [])
                            if inbounds:
                                logger.info(f"get_inbounds attempt {attempt}: got {len(inbounds)} inbounds")
                                return inbounds
                            logger.warning(f"get_inbounds attempt {attempt}: empty inbounds list")
                        else:
                            logger.warning(f"get_inbounds attempt {attempt}: success=false, re-logging in...")
                            self._logged_in = False
                    else:
                        logger.warning(f"get_inbounds attempt {attempt}: HTTP {resp.status}")
            except Exception as e:
                logger.warning(f"get_inbounds attempt {attempt}/{MAX_RETRIES} error: {e}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

        logger.error(f"Failed to get inbounds after {MAX_RETRIES} attempts")
        return []

    # ==================== Client CRUD ====================

    async def add_or_update_client(self, user_id: int, username: str, limit_ip: int = 1,
                                   client_uuid: str = None, sub_id: str = None,
                                   device_name: str = None) -> Optional[dict]:
        """Adds a client to all active 3X-UI inbounds for multi-protocol support."""
        await self._ensure_logged_in()
        session = await self._get_session()

        client_uuid = client_uuid or str(uuid.uuid4())
        email = device_name or f"{username}_{user_id}_{client_uuid[:4]}"
        sub_id = sub_id or client_uuid[:16].replace("-", "")

        client_data = {
            "id": client_uuid,
            "password": client_uuid,
            "alterId": 0,
            "email": email,
            "limitIp": limit_ip,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": user_id,
            "subId": sub_id
        }

        inbounds = await self.get_inbounds()
        if not inbounds:
            logger.error(f"No inbounds found in 3X-UI for URL: {VPN_PANEL_URL}")
            return None

        logger.info(f"Found {len(inbounds)} inbounds to process")

        add_url = f"{VPN_PANEL_URL}/panel/api/inbounds/addClient"
        success = False

        for inbound in inbounds:
            if not inbound.get("enable"):
                continue

            inbound_id = inbound.get("id")
            protocol = inbound.get("protocol", "unknown")
            safe_email = email.replace(" ", "_").replace("#", "").replace("(", "").replace(")", "")
            unique_email = f"{safe_email}_{protocol}_{inbound_id}"

            inbound_client_data = client_data.copy()
            inbound_client_data["email"] = unique_email

            payload = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [inbound_client_data]})
            }

            try:
                async with session.post(add_url, data=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("success"):
                            logger.info(f"Client {unique_email} added to inbound {inbound_id}")
                            success = True
                        else:
                            msg = result.get('msg', 'Unknown error')
                            if "already exists" in msg.lower() or "duplicate" in msg.lower():
                                logger.info(f"Client {unique_email} already exists in inbound {inbound_id}")
                                success = True
                            else:
                                logger.warning(f"Failed to add client {unique_email} to inbound {inbound_id}: {msg}")
                    else:
                        logger.error(f"3X-UI returned status {resp.status} for addClient on inbound {inbound_id}")
            except Exception as e:
                logger.error(f"Exception adding client to inbound {inbound_id}: {e}")

        if success:
            logger.info(f"Client {email} successfully added/verified in 3X-UI")
            return {"uuid": client_uuid, "sub_id": sub_id, "email": email}

        logger.error(f"Failed to add client {email} to any of the {len(inbounds)} inbounds")
        return None

    async def delete_client(self, client_uuid: str) -> bool:
        """Delete a client from all 3X-UI inbounds."""
        await self._ensure_logged_in()
        session = await self._get_session()

        inbounds = await self.get_inbounds()
        if not inbounds:
            return False

        success = False
        for inbound in inbounds:
            inbound_id = inbound.get("id")
            delete_url = f"{VPN_PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}"

            try:
                async with session.post(delete_url) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("success"):
                            logger.info(f"Client {client_uuid} deleted from inbound {inbound_id}")
                            success = True
            except Exception as e:
                logger.error(f"Error deleting client {client_uuid} from inbound {inbound_id}: {e}")

        return success

    async def get_client_traffic(self, sub_id: str) -> Optional[dict]:
        """Fetch traffic statistics for a specific client across all inbounds."""
        inbounds = await self.get_inbounds()
        if not inbounds:
            return None

        up = 0
        down = 0
        total = 0
        enable = False

        for inbound in inbounds:
            client_stats = inbound.get('clientStats', [])
            for stat in client_stats:
                if stat.get('subId') == sub_id:
                    up += stat.get('up', 0)
                    down += stat.get('down', 0)
                    total += stat.get('total', 0)
                    enable = enable or stat.get('enable', False)

        return {
            "up": up,
            "down": down,
            "total": total,
            "enable": enable
        }

    async def get_online_clients(self) -> List[str]:
        """Get list of online client emails."""
        await self._ensure_logged_in()
        session = await self._get_session()

        try:
            url = f"{VPN_PANEL_URL}/panel/api/inbounds/onlines"
            async with session.post(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("obj", []) or []
        except Exception as e:
            logger.error(f"Error getting online clients: {e}")
        return []

    # ==================== Link Generation ====================

    def generate_subscription_link(self, sub_id: str, name: str = "MNVPN") -> str:
        """Generate HTTPS subscription URL for Happ/V2rayNG."""
        sub_url = f"https://{SERVER_DOMAIN}:{SUB_PORT}/sub/{SUB_SECRET}/{sub_id}"
        return sub_url

    def generate_happ_deeplink(self, sub_id: str, name: str = "MNVPN") -> str:
        """Generate Happ deep link with happ:// scheme."""
        sub_url = self.generate_subscription_link(sub_id, name)
        clean_name = name.replace(" ", "_").replace("#", "N")
        deep_link = f"happ://add/{sub_url}#{clean_name}"
        wrapped = f"https://happ.click/?url={deep_link}"
        return wrapped

    def generate_vless_link(self, client_uuid: str, name: str = "MNVPN") -> str:
        """Generate a raw vless:// link for manual import/QR."""
        pbk = "Dodq32f0P7YVGHkvdI-njibzKlibaShzqkBrglCDEyA"
        sid = "0c539e1b54f35027"
        sni = "www.microsoft.com"
        clean_name = name.replace(" ", "_").replace("#", "N")

        vless = (
            f"vless://{client_uuid}@{SERVER_DOMAIN}:443?"
            f"encryption=none&security=reality&sni={sni}&"
            f"fp=chrome&pbk={pbk}&sid={sid}&"
            f"flow=xtls-rprx-vision&type=tcp#{clean_name}"
        )
        return vless

    def generate_config_file(self, client_uuid: str, sub_id: str) -> bytes:
        """Generate a JSON config file for manual import."""
        config = {
            "dns": {"servers": ["1.1.1.1", "8.8.8.8"]},
            "inbounds": [{
                "port": 10808,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True}
            }],
            "outbounds": [{
                "protocol": "vless",
                "settings": {"vnext": [{
                    "address": SERVER_IP,
                    "port": 443,
                    "users": [{"id": client_uuid, "encryption": "none", "flow": "xtls-rprx-vision"}]
                }]},
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "fingerprint": "chrome",
                        "serverName": "www.microsoft.com",
                        "publicKey": "Dodq32f0P7YVGHkvdI-njibzKlibaShzqkBrglCDEyA",
                        "shortId": "0c539e1b54f35027",
                        "spiderX": "/"
                    }
                }
            }]
        }
        return json.dumps(config, indent=2, ensure_ascii=False).encode('utf-8')

    # ==================== QR Code ====================

    def generate_qr_code(self, data: str) -> Optional[bytes]:
        """Generate styled QR code in brand colors."""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="#4B0082", back_color="white")
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            return img_bytes.read()
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return None

    # ==================== Device Registration ====================

    async def register_device(self, user_id: int, username: str, device_name: str = None,
                              limit_ip: int = 1) -> Optional[Dict]:
        """Register a new device for user. Returns device info including links."""
        await self._ensure_logged_in()
        device_id = str(uuid.uuid4())
        device_name = device_name or f"Устройство {device_id[:6]}"

        xui_data = await self.add_or_update_client(
            user_id, username, limit_ip,
            client_uuid=None, sub_id=None,
            device_name=device_name
        )

        if not xui_data:
            return None

        await add_device(
            device_id=device_id,
            user_id=user_id,
            device_name=device_name,
            uuid=xui_data["uuid"],
            sub_id=xui_data["sub_id"]
        )

        sub_link = self.generate_subscription_link(xui_data["sub_id"], device_name)
        vless_link = self.generate_vless_link(xui_data["uuid"], device_name)
        happ_link = self.generate_happ_deeplink(xui_data["sub_id"], device_name)

        qr_code_bytes = self.generate_qr_code(vless_link)
        config_bytes = self.generate_config_file(xui_data["uuid"], xui_data["sub_id"])

        return {
            "device_id": device_id,
            "device_name": device_name,
            "uuid": xui_data["uuid"],
            "sub_id": xui_data["sub_id"],
            "subscription_link": sub_link,
            "vless_link": vless_link,
            "happ_link": happ_link,
            "qr_code": qr_code_bytes,
            "config_file": config_bytes
        }

    async def remove_device(self, device_id: str) -> bool:
        """Remove a device and delete from 3X-UI."""
        from database import get_device
        device = await get_device(device_id)
        if not device:
            return False

        client_uuid = device['uuid']
        deleted = await self.delete_client(client_uuid)

        if deleted:
            await deactivate_device(device_id)
            logger.info(f"Device {device_id} removed")
            return True
        return False


vpn_service = VPNService()
