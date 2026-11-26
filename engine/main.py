import os
import sys

_base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)

import re
import json

def compute_username(custom_username: str, idx: int, auto_increment: bool = True) -> str:
    """
    Compute username for account index `idx`.
    If custom_username ends with digits (e.g. 'kaf100000'), smart-increments the number:
    idx 0: kaf100000
    idx 1: kaf100001
    idx 2: kaf100002
    """
    if not custom_username:
        return ""
    if not auto_increment:
        return custom_username

    match = re.search(r"^(.*?)(\d+)$", custom_username)
    if match:
        prefix = match.group(1)
        digits_str = match.group(2)
        base_num = int(digits_str)
        pad_len = len(digits_str)
        return f"{prefix}{str(base_num + idx).zfill(pad_len)}"
    else:
        return f"{custom_username}{idx + 1}"

class AccountNameProvider:
    """Thread-safe atomic username distributor"""
    def __init__(self, base_username: str, auto_increment: bool = True):
        self.base_username = base_username
        self.auto_increment = auto_increment
        self.counter = 0
        self.lock = threading.Lock()

    def get_next_username(self):
        if not self.base_username:
            return None
        with self.lock:
            idx = self.counter
            self.counter += 1
        if self.auto_increment:
            return compute_username(self.base_username, idx, auto_increment=True)
        else:
            return self.base_username


"""
Pokemon Auto Register Tool - Main Entry Point
Based on ANALYSIS-poke-dai-chien.md

IMPORTANT: This tool is incomplete and for educational purposes only.
The exact request format and signature algorithm need to be verified
by analyzing the Dart code with blutter.
"""

import logging
import sys
import time
import random
import argparse
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

from device_fingerprint import DeviceFingerprint
from request_signer import RequestSigner
from api_client import APIClient
from account_generator import AccountGenerator
from game_socket_client import GameSocketClient
from activity_claim_client import ActivityClaimClient
from db_manager import DatabaseManager
from config import RATE_LIMIT, DEFAULT_GAME_ZONE_ID
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

def parse_proxy(raw_proxy: str, default_type: str = "http") -> Optional[dict]:
    if not raw_proxy:
        return None
    raw = raw_proxy.strip()
    if not raw or raw.startswith("#"):
        return None

    proxy_type = default_type.lower()
    if "://" in raw:
        scheme, remainder = raw.split("://", 1)
        proxy_type = scheme.lower()
        raw = remainder

    parts = raw.split(":")
    if len(parts) == 4:
        host, port_str, username, password = parts
        try:
            port = int(port_str)
            return {
                "type": proxy_type,
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "url": f"{proxy_type}://{username}:{password}@{host}:{port}"
            }
        except ValueError:
            return None
    elif len(parts) == 2:
        if "@" in raw:
            auth_part, host_port = raw.rsplit("@", 1)
            u_parts = auth_part.split(":", 1)
            username = u_parts[0]
            password = u_parts[1] if len(u_parts) > 1 else None
            h_parts = host_port.split(":")
            host = h_parts[0]
            try:
                port = int(h_parts[1])
                return {
                    "type": proxy_type,
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password,
                    "url": f"{proxy_type}://{username}:{password}@{host}:{port}"
                }
            except ValueError:
                return None
        else:
            host, port_str = parts
            try:
                port = int(port_str)
                return {
                    "type": proxy_type,
                    "host": host,
                    "port": port,
                    "username": None,
                    "password": None,
                    "url": f"{proxy_type}://{host}:{port}"
                }
            except ValueError:
                return None
    elif "@" in raw:
        auth_part, host_port = raw.rsplit("@", 1)
        u_parts = auth_part.split(":", 1)
        username = u_parts[0]
        password = u_parts[1] if len(u_parts) > 1 else None
        h_parts = host_port.split(":")
        host = h_parts[0]
        port = int(h_parts[1]) if len(h_parts) > 1 else (1080 if proxy_type == "socks5" else 8080)
        return {
            "type": proxy_type,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "url": f"{proxy_type}://{username}:{password}@{host}:{port}"
        }
    return None


try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

_THREAD_LOG_CTX = threading.local()


class ThreadAwareFormatter(logging.Formatter):
    def format(self, record):
        msg_out = super().format(record)
        prefix = getattr(_THREAD_LOG_CTX, "prefix", "")
        if prefix and "[Luồng #" not in record.getMessage():
            parts = msg_out.split(" - ", 2)
            if len(parts) == 3:
                return f"{parts[0]} - {parts[1]} - {prefix}{parts[2]}"
        return msg_out


class FlushStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


_log_formatter = ThreadAwareFormatter('%(asctime)s - %(levelname)s - %(message)s')
_stream_handler = FlushStreamHandler(sys.stdout)
_stream_handler.setFormatter(_log_formatter)
_log_handlers: List[logging.Handler] = [_stream_handler]
try:
    _log_path = Path(os.environ.get("POKEMON_LOG_PATH") or (Path(__file__).resolve().parent.parent / "data" / "auto_register.log"))
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _file_handler = logging.FileHandler(str(_log_path), encoding='utf-8')
    _file_handler.setFormatter(_log_formatter)
    _log_handlers.insert(0, _file_handler)
except Exception:
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    handlers=_log_handlers
)
logger = logging.getLogger(__name__)


class AutoRegisterTool:
    """Main registration automation tool"""
    
    def __init__(
        self,
        dry_run: bool = False,
        default_zone: str = DEFAULT_GAME_ZONE_ID,
        max_per_minute: int = None,
        threads: int = 1,
        proxies: Optional[List[dict]] = None
    ):
        self.max_per_minute = max_per_minute
        self.threads = max(1, threads)
        self.proxies = proxies or []
        self.db_lock = threading.Lock()
        self.api_client = APIClient(max_per_minute=max_per_minute)
        self.signer = RequestSigner()
        self.account_gen = AccountGenerator()
        self.socket_client = GameSocketClient()
        self.activity_client = ActivityClaimClient()
        self.db = DatabaseManager()
        self.dry_run = dry_run
        self.default_zone = default_zone
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No actual requests will be sent")
    
    def test_connection(self) -> bool:
        """Test API connectivity"""
        logger.info("Testing API connection...")
        
        # Create test device
        device = DeviceFingerprint()
        device_info = device.to_api_dict()
        
        # Build test request
        test_body = self.signer.build_register_body(
            username="test_user_" + str(int(time.time())),
            plaintext_password="test123456",
            device_info=device_info
        )
        
        if self.dry_run:
            logger.info("✅ Dry run: Would send test request")
            logger.info(f"Device: {device.model}")
            logger.info(f"Request keys: {list(test_body.keys())}")
            logger.info(f"Sign: {test_body.get('sign', 'N/A')[:20]}...")
            return True
        
        # In real mode, we won't actually test to avoid creating junk accounts
        logger.info("⚠️  Real mode: skipping test to avoid creating test account")
        logger.info(f"Ready to register with device: {device.model}")
        return True
    
    def register_single_account(
        self,
        account_data: dict = None,
        visitor_mode: bool = False,
        visitor_upgrade: bool = True,
        claim_mail: bool = True,
        auto_draw: bool = True,
        game_zone_id: str = None,
        custom_username: str = None,
        custom_password: str = None,
        proxy_info: Optional[dict] = None,
        thread_id: Optional[int] = None,
        auto_increment: bool = True,
        name_provider: Optional[Any] = None
    ) -> dict:
        """
        Register a single account, bind to game zone, create character, claim mailbox, and auto-draw lottery.
        
        Flows:
        1. VISITOR UPGRADE (Default & Recommended):
           - initSDK()
           - register(userName="") -> creates visitor account with userId
           - bindVisitor() -> upgrades visitor to permanent username & password (triggers 20 ticket event reward!)
           - login() -> acquires permanent authentication token
           - bindZone() -> binds account to game zone
           - create_character() -> sets role name via TCP socket
           - claim_mailbox() -> claims 20 tickets & rewards, cleans mailbox
           - auto_lottery_draw_stream() -> automatically draws 21 times (1 free + 1x X10 + 10x X1)
        
        2. NORMAL REGISTER:
           - initSDK() -> register() -> login() -> bindZone() -> create_character() -> claim_mailbox() -> auto_draw()
        
        3. VISITOR ONLY:
           - initSDK() -> register(userName="") -> bindZone()
        """
        # Generate device fingerprint
        device = DeviceFingerprint()
        device_info = device.to_api_dict()

        # Setup isolated clients per-thread / per-proxy with consistent device telemetry
        t_prefix = f"[Luồng #{thread_id}] " if thread_id else ""
        api_client = APIClient(max_per_minute=self.max_per_minute, proxy=proxy_info)
        socket_client = GameSocketClient(proxy=proxy_info, device_telemetry=device_info)
        activity_client = ActivityClaimClient(proxy=proxy_info)
        
        # STEP 1: Initialize SDK
        logger.info("📡 Step 1: Initializing SDK...")
        init_body = self.signer.build_init_sdk_body(device_info, first_install=True)
        
        if not self.dry_run:
            success, init_response, error = api_client.init_sdk(init_body)
            if not success:
                logger.error(f"❌ Bước 1 (Init SDK) thất bại: {error}. Bỏ tài khoản này theo quy tắc Fail-Fast.")
                return {"success": False, "error": f"Init SDK failed: {error}"}
            else:
                logger.info("✅ SDK initialized")
                time.sleep(random.uniform(0.7, 1.5))
        else:
            logger.info("✅ Dry run: Would initialize SDK")
        
        target_zone = str(game_zone_id if game_zone_id is not None else self.default_zone)

        # Prepare Account Data
        if account_data is None:
            account_data = self.account_gen.generate_account()
        username = custom_username or account_data["username"]
        password = custom_password or account_data["password"]
        char_name = account_data.get("character_name") or self.account_gen.generate_character_name()

        # STEP 2: Registration based on mode
        if visitor_mode:
            # Visitor only mode
            request_body = self.signer.build_visitor_register_body(device_info)
            v_pwd = request_body.pop("_plaintext_password", "pass1234")
            logger.info("📝 Step 2: Registering Visitor account...")
            if self.dry_run:
                return {"success": True, "account": {"username": "(visitor)", "password": v_pwd}}
            success, response_data, error = api_client.register(request_body)
            if not success:
                return {"success": False, "error": error}
            user_id = response_data.get("data", {}).get("userId")
            v_user = response_data.get("data", {}).get("userName", "")
            # Login to get token
            l_body = self.signer.build_login_body(v_user, v_pwd, device_info)
            _, l_res, _ = api_client.login(l_body)
            token = l_res.get("token") or l_res.get("data", {}).get("token", "N/A")
            result = {
                "success": True,
                "account": {"username": v_user, "password": v_pwd, "character_name": "visitor"},
                "device": device_info,
                "token": token,
                "user_id": user_id,
                "game_zone_id": target_zone
            }
            return result

        elif visitor_upgrade:
            # Recommended flow: Register Visitor -> Upgrade via bindVisitor -> Get 20 tickets event mail!
            logger.info(f"📝 Step 2: Creating account via Visitor Upgrade flow (Enables 20 Ticket Event Reward)...")
            logger.info(f"   Target Username: {username} | Role Name: {char_name}")
            time.sleep(random.uniform(0.6, 1.2))
            
            if self.dry_run:
                logger.info("✅ Dry run: Would register visitor and upgrade to full account")
                return {
                    "success": True,
                    "account": {"username": username, "password": password, "character_name": char_name},
                    "token": "DRY_RUN_TOKEN",
                    "user_id": "DRY_RUN_UID",
                    "game_zone_id": target_zone
                }

            # 2a. Register visitor
            v_body = self.signer.build_visitor_register_body(device_info)
            v_pwd = v_body.pop("_plaintext_password", "pass1234")
            v_success, v_resp, v_err = api_client.register(v_body)
            if not v_success or not v_resp or "data" not in v_resp:
                logger.error(f"❌ Failed to create initial visitor: {v_err}")
                return {"success": False, "error": f"Visitor creation failed: {v_err}"}

            user_id = v_resp["data"]["userId"]
            temp_visitor_name = v_resp["data"].get("userName", "")
            logger.info(f"   ✅ Initial visitor created: UID={user_id} (temp: {temp_visitor_name})")
            time.sleep(random.uniform(0.7, 1.4))

            # 2b. Upgrade visitor via bindVisitor with smart retry on duplicate name (both Random & Auto-Increment modes)
            max_bind_retries = 5 if (not custom_username or auto_increment) else 1
            curr_target_user = username
            bv_success = False
            bv_resp = None
            bv_err = ""

            for bind_attempt in range(max_bind_retries):
                logger.info(f"   🔄 Upgrading visitor {user_id} to official account '{curr_target_user}'...")
                bind_v_body = self.signer.build_bind_visitor_body(
                    user_id=str(user_id),
                    username=curr_target_user,
                    plaintext_password=password,
                    device_info=device_info
                )
                bv_success, bv_resp, bv_err = api_client.bind_visitor(bind_v_body)
                if bv_success:
                    username = curr_target_user
                    break

                # If username already taken (error 108), generate a new random name or advance increment
                err_str = str(bv_err).lower()
                if "108" in err_str or "user has bind" in err_str or "tồn tại" in err_str:
                    logger.warning(f"   ⚠️ Tên '{curr_target_user}' đã tồn tại trên game server (Error 108).")
                    if bind_attempt < max_bind_retries - 1:
                        if not custom_username:
                            new_rand_user = self.account_gen.generate_account()["username"]
                            if new_rand_user == curr_target_user:
                                new_rand_user = self.account_gen.generate_account()["username"]
                            curr_target_user = new_rand_user
                            logger.info(f"   🔄 Tự động random tên đăng nhập mới: '{curr_target_user}'")
                        elif name_provider:
                            curr_target_user = name_provider.get_next_username()
                            logger.info(f"   🔄 Bốc số mới an toàn từ hàng đợi chung: '{curr_target_user}'")
                        else:
                            curr_target_user = compute_username(curr_target_user, 1, auto_increment=True)
                else:
                    break

            if not bv_success:
                logger.error(f"❌ Failed to upgrade visitor: {bv_err}")
                return {"success": False, "error": f"bindVisitor failed: {bv_err}"}

            logger.info(f"   🎉 Account '{username}' upgraded successfully! Event rewards unlocked.")

            # 2c. Login to acquire permanent token
            l_body = self.signer.build_login_body(username=username, plaintext_password=password, device_info=device_info)
            l_success, l_data, l_err = api_client.login(l_body)
            token = "N/A"
            if l_success and l_data:
                token = l_data.get("token") or l_data.get("data", {}).get("token") or "N/A"

            result = {
                "success": True,
                "account": {"username": username, "password": password, "character_name": char_name},
                "device": device_info,
                "token": token,
                "user_id": str(user_id),
                "game_zone_id": target_zone
            }

        else:
            # Normal direct registration
            request_body = self.signer.build_register_body(
                username=username,
                plaintext_password=password,
                device_info=device_info
            )
            logger.info(f"📝 Step 2: Registering direct account: {username}")
            logger.info(f"   Role Name: {char_name}")
            
            if self.dry_run:
                return {
                    "success": True,
                    "account": {"username": username, "password": password, "character_name": char_name},
                    "token": "DRY_RUN_TOKEN",
                    "user_id": "DRY_RUN_UID",
                    "game_zone_id": target_zone
                }

            success, response_data, error = api_client.register(request_body)
            if not success:
                logger.error(f"❌ Failed: {username} - {error}")
                return {"success": False, "error": error}

            data = response_data.get("data", response_data)
            user_id = str(data.get("userId") or data.get("user_id") or "N/A")
            token = data.get("token") or "N/A"

            # Login if token missing
            if token == "N/A":
                l_body = self.signer.build_login_body(username=username, plaintext_password=password, device_info=device_info)
                l_succ, l_data, _ = api_client.login(l_body)
                if l_succ and l_data:
                    token = l_data.get("token") or l_data.get("data", {}).get("token") or "N/A"

            result = {
                "success": True,
                "account": {"username": username, "password": password, "character_name": char_name},
                "device": device_info,
                "token": token,
                "user_id": user_id,
                "game_zone_id": target_zone
            }

        # Common Steps 3, 4, 5 for all active accounts:
        logger.info(f"✅ Account ready: {username} (UID: {result['user_id']})")

        # STEP 3: Bind to game zone
        time.sleep(random.uniform(0.8, 1.8))
        logger.info(f"🌐 Step 3: Binding user {result['user_id']} to zone {target_zone}...")
        bind_body = self.signer.build_bind_zone_body(
            user_id=result["user_id"],
            game_zone_id=target_zone,
            create_role=True
        )
        b_success, b_data, b_error = api_client.bind_zone(bind_body)
        if b_success:
            logger.info(f"   ✅ Bound to zone {target_zone} successfully")
            result["game_zone_id"] = target_zone
        else:
            logger.error(f"❌ Bước 3 (Gán Server Zone {target_zone}) thất bại: {b_error}. Bỏ tài khoản này theo quy tắc Fail-Fast.")
            result["bind_error"] = b_error
            result["success"] = False
            return result

        dev_str = (
            device_info.get('deviceNo')
            or device_info.get('device')
            or device_info.get('visitor_id')
            or hashlib.md5(f"DEV_{result['user_id']}".encode()).hexdigest()[:16]
        )

        # STEP 4: Create Character on Game Server via Socket (Stage 3) with smart duplicate retry
        if char_name:
            time.sleep(random.uniform(1.8, 3.2))
            max_char_retries = 5
            current_char_name = char_name
            c_success = False
            c_msg = ""

            for char_attempt in range(1, max_char_retries + 1):
                attempt_str = f" (Lần {char_attempt}/{max_char_retries})" if char_attempt > 1 else ""
                logger.info(f"🎮 Step 4: Creating character '{current_char_name}' on zone {target_zone} via Socket{attempt_str}...")
                c_success, c_msg = socket_client.create_character(
                    user_id=result["user_id"],
                    character_name=current_char_name,
                    game_zone_id=target_zone,
                    device_id=f"DEVICE#{dev_str}",
                    token=result.get("token"),
                    claim_mail=False
                )
                if c_success:
                    logger.info(f"   ✨ Character created on server: {current_char_name}")
                    result["account"]["character_name"] = current_char_name
                    result["character_created"] = True
                    break
                else:
                    if char_attempt < max_char_retries:
                        c_msg_low = str(c_msg).lower()
                        is_net_err = any(
                            k in c_msg_low
                            for k in ("socket error", "winerror", "handshake", "timed out", "timeout", "forcibly closed", "aborted")
                        )
                        if is_net_err:
                            logger.info(f"   ℹ️ Kết nối tạo nhân vật '{current_char_name}' gián đoạn ({c_msg}), đợi nhẹ rồi kết nối lại...")
                            time.sleep(1.2)
                        else:
                            logger.info(f"   ℹ️ Tên '{current_char_name}' chưa tạo được ({c_msg}), đang đổi tên mới...")
                            new_name = self.account_gen.generate_character_name()
                            if new_name == current_char_name:
                                new_name = self.account_gen.generate_character_name()
                            current_char_name = new_name
                            time.sleep(0.5)
                    else:
                        logger.warning(f"   ⚠️ Tạo nhân vật '{current_char_name}' không thành công sau {max_char_retries} lần thử: {c_msg}")

            if not c_success:
                logger.error(f"   ❌ Tạo nhân vật thất bại sau {max_char_retries} lần thử: {c_msg}")
                result["character_error"] = c_msg
                result["success"] = False
                return result

        # STEP 5: Trigger Web Activity Reward API (Sends 'Thưởng nâng cấp tk du khách' 20 tickets to mailbox)
        if claim_mail and result.get("character_created"):
            time.sleep(random.uniform(1.8, 3.0))
            logger.info("🎁 Step 5: Triggering Web Activity Event Reward ('Thưởng nâng cấp tk du khách')...")
            w_succ, w_msg = activity_client.claim_event_reward(
                username=username,
                plaintext_password=password,
                socket_zone_id=target_zone
            )
            result["web_reward_status"] = w_msg
            if not w_succ:
                logger.warning(f"⚠️ Bước 5 (Nhận 20 vé Web) chưa thành công: {w_msg}.")
                logger.info(f"💾 Đã lưu tài khoản '{username}' vào hàng chờ [Chờ nhận vé] để chạy tiếp sau!")
                result["status"] = "pending_reward"
                result["pets"] = []
                result["web_reward_error"] = w_msg
                self.export_single_account(result)
                return result

            time.sleep(random.uniform(1.5, 2.8))

            # STEP 6: Connect to TCP Socket to Claim Mailbox Rewards & 20 tickets & Auto Draw
            logger.info("📬 Step 6: Connecting to Game Server Socket to claim mailbox rewards...")
            m_succ, m_msg, items, draw_res = socket_client.claim_mailbox(
                user_id=result["user_id"],
                token=result.get("token"),
                game_zone_id=target_zone,
                device_id=f"DEVICE#{dev_str}",
                auto_draw=auto_draw
            )
            result["mailbox_status"] = m_msg
            result["claimed_items"] = items
            result["lottery_draws"] = draw_res
            result["pets"] = draw_res.get("pets", [])
            result["lucky_sigh"] = draw_res.get("lucky_sigh", "")

            if not m_succ:
                logger.warning(f"⚠️ Bước 6 (Nhận thư & Ấp pet) chưa thành công: {m_msg}.")
                logger.info(f"💾 Đã lưu tài khoản '{username}' vào hàng chờ [Chờ rút pet] để chạy tiếp sau!")
                result["status"] = "pending_draw"
                self.export_single_account(result)
                return result

        result["status"] = "completed"
        # Chỉ lưu vào SQLite khi đã hoàn thành toàn bộ các bước thành công
        if result.get("success"):
            try:
                self.export_single_account(result)
            except Exception as ex:
                logger.debug(f"SQLite save failed: {ex}")

        return result
    
    def register_batch(
        self,
        count: int,
        delay_range: tuple = None,
        visitor_mode: bool = False,
        visitor_upgrade: bool = True,
        claim_mail: bool = True,
        auto_draw: bool = True,
        game_zone_id: str = None,
        custom_username: str = None,
        custom_password: str = None,
        output_file: str = None,
        auto_increment: bool = True
    ) -> list:
        """Register multiple accounts with concurrent multi-threading & proxy support"""
        if delay_range is None:
            delay_range = (RATE_LIMIT["delay_min"], RATE_LIMIT["delay_max"])
        
        mode_str = "VISITOR_ONLY" if visitor_mode else ("VISITOR_UPGRADE" if visitor_upgrade else "NORMAL")
        target_zone = str(game_zone_id if game_zone_id is not None else self.default_zone)
        total_proxies = len(self.proxies)
        
        logger.info(f"🚀 Starting batch registration: {count} accounts ({mode_str} mode, Zone: {target_zone})")
        logger.info(f"⚡ Số luồng đồng thời: {self.threads} luồng")
        if total_proxies > 0:
            logger.info(f"🌐 Danh sách proxy: {total_proxies} proxy được phân bổ xoay vòng")
        else:
            logger.info("🌐 Chế độ mạng: Trực tiếp (Direct Network)")

        if custom_username:
            logger.info(f"   Custom Username: '{custom_username}'" + (f" (suffix 1..{count})" if count > 1 else ""))
        if custom_password:
            logger.info(f"   Custom Password: (fixed custom password configured)")
        logger.info(f"   Mailbox Auto-Claim: {'ENABLED ✅' if claim_mail else 'DISABLED ❌'}")
        logger.info(f"   21-Lottery Auto-Draw: {'ENABLED ✅' if auto_draw else 'DISABLED ❌'}")
        logger.info(f"   Delay range: {delay_range[0]}-{delay_range[1]}s")

        results = []
        success_count = 0

        if self.threads > 1 and count > 1:
            logger.info(f"⚡ Khởi chạy {self.threads} luồng worker song song...")
            name_provider = AccountNameProvider(custom_username, auto_increment) if custom_username else None
            worker_slot_lock = threading.Lock()
            worker_slot_seq = [0]

            def worker_task(idx: int):
                worker_thread = getattr(_THREAD_LOG_CTX, "worker_slot", None)
                if worker_thread is None:
                    with worker_slot_lock:
                        worker_slot_seq[0] += 1
                        worker_thread = worker_slot_seq[0]
                    _THREAD_LOG_CTX.worker_slot = worker_thread
                _THREAD_LOG_CTX.prefix = f"[Luồng #{worker_thread}] "
                try:
                    # Wave startup stagger: 0.35s per thread to prevent socket handshake collisions & proxy box NAT congestion
                    if idx < self.threads and worker_thread > 1:
                        stagger = 0.35 if total_proxies > 0 else 0.45
                        time.sleep(stagger * (worker_thread - 1))

                    current_user = name_provider.get_next_username() if name_provider else None
                    current_pass = custom_password if custom_password else None

                    if total_proxies > 0:
                        p_idx = (worker_thread - 1) % total_proxies if total_proxies == self.threads else (idx % total_proxies)
                        proxy_info = self.proxies[p_idx]
                    else:
                        proxy_info = None
                    p_desc = f" | Proxy: {proxy_info['host']}:{proxy_info['port']}" if proxy_info else " | Mạng gốc"
                    logger.info(f"[Luồng #{worker_thread}] [Tài khoản {idx+1}/{count}]{p_desc}")

                    res = self.register_single_account(
                        visitor_mode=visitor_mode,
                        visitor_upgrade=visitor_upgrade,
                        claim_mail=claim_mail,
                        auto_draw=auto_draw,
                        game_zone_id=target_zone,
                        custom_username=current_user,
                        custom_password=current_pass,
                        proxy_info=proxy_info,
                        thread_id=worker_thread,
                        auto_increment=auto_increment,
                        name_provider=name_provider
                    )
                    self.export_single_account(res, filename=output_file)

                    # Delay between accounts for this worker
                    if delay_range and idx + self.threads < count:
                        d = random.uniform(*delay_range)
                        time.sleep(d)

                    return res
                finally:
                    _THREAD_LOG_CTX.prefix = ""

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
                # Dung cua so truot (sliding window) de tranh tao hang trieu Future trong RAM gay OOM sap may chu
                max_in_flight = max(self.threads * 2, 20)
                active_futures = set()
                task_iter = iter(range(count))

                # Dua truoc so luong task tuong ung voi so luong dang chay vao pool
                for _ in range(min(count, max_in_flight)):
                    idx = next(task_iter, None)
                    if idx is not None:
                        active_futures.add(executor.submit(worker_task, idx))

                while active_futures:
                    done, active_futures = concurrent.futures.wait(
                        active_futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for future in done:
                        try:
                            r = future.result()
                            if r and r.get("success"):
                                success_count += 1
                            # Gioi han danh sach ket qua luu trong RAM toi da 500 ban ghi de tiet kiem bo nho
                            if len(results) < 500:
                                results.append(r)
                        except Exception as e:
                            logger.error(f"❌ Lỗi luồng thực thi: {e}")

                        next_idx = next(task_iter, None)
                        if next_idx is not None:
                            active_futures.add(executor.submit(worker_task, next_idx))
        else:
            # Sequential 1 thread
            for i in range(count):
                logger.info(f"\n{'='*60}")
                proxy_info = self.proxies[i % total_proxies] if total_proxies > 0 else None
                p_desc = f" | Proxy: {proxy_info['host']}:{proxy_info['port']}" if proxy_info else ""
                logger.info(f"[{i+1}/{count}]{p_desc}")

                current_user = None
                if custom_username:
                    current_user = compute_username(custom_username, i, auto_increment)
                current_pass = custom_password if custom_password else None

                result = self.register_single_account(
                    visitor_mode=visitor_mode,
                    visitor_upgrade=visitor_upgrade,
                    claim_mail=claim_mail,
                    auto_draw=auto_draw,
                    game_zone_id=target_zone,
                    custom_username=current_user,
                    custom_password=current_pass,
                    proxy_info=proxy_info,
                    thread_id=1,
                    auto_increment=auto_increment
                )
                results.append(result)
                if result.get("success"):
                    success_count += 1

                self.export_single_account(result, filename=output_file)

                if i < count - 1:
                    delay = random.uniform(*delay_range)
                    logger.info(f"⏱️  Waiting {delay:.1f}s...")
                    time.sleep(delay)

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 BATCH SUMMARY:")
        logger.info(f"   Total: {count}")
        logger.info(f"   Success: {success_count} ✅")
        logger.info(f"   Failed: {count - success_count} ❌")
        if count > 0:
            logger.info(f"   Success Rate: {(success_count/count)*100:.1f}%")

        return results

    def export_single_account(self, result: dict, filename: Optional[str] = None):
        """Export a single successful registration immediately to SQLite (and optional file)"""
        if self.dry_run:
            return
        status = result.get("status", "completed" if result.get("success") else "failed")
        if status not in ("completed", "pending_reward", "pending_draw") and not result.get("success"):
            return

        acc = result["account"]

        # 1. Save to SQLite database (deduplicated per result dict to avoid double writes)
        if not result.get("_db_saved"):
            try:
                with self.db_lock:
                    self.db.save_account(result)
                result["_db_saved"] = True
                logger.info(f"💾 Đã lưu tài khoản '{acc['username']}' vào SQLite Database")
            except Exception as e:
                logger.debug(f"SQLite save error: {e}")

        # 2. Append to text file if explicitly requested
        if filename and not result.get("_file_saved"):
            file_path = Path(filename)
            file_exists = file_path.exists() and file_path.stat().st_size > 0
            token = result.get("token", "N/A")
            user_id = result.get("user_id", "N/A")
            zone_id = result.get("game_zone_id", "N/A")
            char_name = acc.get("character_name", "N/A")
            pets = result.get("pets", [])
            pets_str = f":[{','.join(pets)}]" if pets else ""
            line = f"{acc['username']}:{acc['password']}:{token}:{user_id}:{zone_id}:{char_name}{pets_str}\n"

            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    if not file_exists:
                        f.write("# Pokemon Auto Register - Exported Accounts\n")
                        f.write("# Format: username:password:token:user_id:game_zone_id:character_name:pets\n\n")
                    f.write(line)
                result["_file_saved"] = True
            except Exception as e:
                logger.debug(f"File save error: {e}")
    

    def resume_pending_accounts(
        self,
        target_username: Optional[str] = None,
        auto_draw: bool = True
    ) -> list:
        """
        Resume processing for accounts stuck in 'pending_reward' or 'pending_draw'.
        Step 5 (Web Activity Claim) -> Step 6 (Mailbox Claim & 21-Lottery Draw).
        Fully supports multi-threading and proxy allocation according to user configuration!
        """
        accounts = self.db.get_all_accounts()
        pending = [
            a for a in accounts
            if a.get("status") in ("pending_reward", "pending_draw") and
               (not target_username or a["username"] == target_username)
        ]

        if not pending:
            logger.info("ℹ️ Không tìm thấy tài khoản nào đang chờ nhận vé hoặc chờ rút pet.")
            return []

        num_workers = max(1, min(self.threads, len(pending)))
        total_proxies = len(self.proxies)
        logger.info(f"⚡ Bắt đầu chạy tiếp cho {len(pending)} tài khoản đang chờ ({num_workers} luồng đồng thời, {total_proxies} proxy)...")
        results = []

        resume_slot_lock = threading.Lock()
        resume_slot_seq = [0]

        def _process_single_pending(item):
            idx, acc, fallback_wid = item
            if num_workers > 1:
                worker_id = getattr(_THREAD_LOG_CTX, "resume_slot", None)
                if worker_id is None:
                    with resume_slot_lock:
                        resume_slot_seq[0] += 1
                        worker_id = resume_slot_seq[0]
                    _THREAD_LOG_CTX.resume_slot = worker_id
                _THREAD_LOG_CTX.prefix = f"[Luồng #{worker_id}] "
            else:
                worker_id = fallback_wid
                _THREAD_LOG_CTX.prefix = ""
            try:
                username = acc["username"]
                password = acc["password"]
                user_id = acc["user_id"]
                zone_id = acc["zone_id"]
                token = acc["token"]
                char_name = acc["character_name"]
                status = acc["status"]

                # Assign proxy round-robin (or 1-to-1 per worker when counts match)
                proxy_info = None
                if self.proxies:
                    p_idx = (worker_id - 1) % len(self.proxies) if len(self.proxies) == num_workers else ((idx - 1) % len(self.proxies))
                    proxy_info = self.proxies[p_idx]

                p_ip = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Mạng gốc"
                t_prefix = f"[Luồng #{worker_id} | {p_ip}] "

                logger.info(f"{t_prefix}[Tài khoản {idx}/{len(pending)}] 🔄 Chạy tiếp tài khoản: {username} (Trạng thái: {status}, Zone: {zone_id})...")

                dev = DeviceFingerprint()
                socket_client = GameSocketClient(proxy=proxy_info, device_telemetry=dev.to_api_dict())
                activity_client = ActivityClaimClient(proxy=proxy_info)
                dev_str = hashlib.md5(f"DEV_{user_id}".encode()).hexdigest()[:16]

                # If stuck at Step 5: Try claim web reward
                if status == "pending_reward":
                    logger.info(f"{t_prefix}🎁 Step 5: Thử lại Web Activity Event Reward ('Thưởng nâng cấp tk du khách') cho {username}...")
                    w_succ, w_msg = activity_client.claim_event_reward(
                        username=username,
                        plaintext_password=password,
                        socket_zone_id=zone_id
                    )
                    if not w_succ:
                        logger.warning(f"{t_prefix}⏳ Máy chủ web vẫn chưa đồng bộ: {w_msg}. Giữ nguyên tài khoản ở hàng chờ để thử lại sau.")
                        return {"username": username, "success": False, "status": "pending_reward", "message": w_msg}
                    logger.info(f"{t_prefix}✅ Đã kích hoạt 20 vé web thành công cho {username}!")
                    status = "pending_draw"

                # Step 6: Socket mailbox claim & auto draw
                if status == "pending_draw":
                    logger.info(f"{t_prefix}📬 Step 6: Kết nối socket để nhận 20 vé & rút pet cho {username}...")
                    prior_pets = acc.get("pets") or []
                    m_succ, m_msg, items, draw_res = socket_client.claim_mailbox(
                        user_id=user_id,
                        token=token,
                        game_zone_id=zone_id,
                        device_id=f"DEVICE#{dev_str}",
                        auto_draw=auto_draw,
                        allow_bag_sweep=True,
                        has_partial_draws=(len(prior_pets) > 0)
                    )

                    if not m_succ:
                        partial_pets = draw_res.get("pets") if isinstance(draw_res, dict) else None
                        if partial_pets:
                            with self.db_lock:
                                self.db.save_account({
                                    "success": False,
                                    "status": "pending_draw",
                                    "account": {"username": username, "password": password, "character_name": char_name},
                                    "token": token,
                                    "user_id": user_id,
                                    "game_zone_id": zone_id,
                                    "pets": partial_pets
                                })
                        logger.warning(f"{t_prefix}⚠️ Chưa rút xong pet qua socket: {m_msg}.")
                        return {"username": username, "success": False, "status": "pending_draw", "message": m_msg}

                    pets = draw_res.get("pets", [])
                    lucky_sigh = draw_res.get("lucky_sigh", "")
                    update_result = {
                        "success": True,
                        "status": "completed",
                        "account": {"username": username, "password": password, "character_name": char_name},
                        "token": token,
                        "user_id": user_id,
                        "game_zone_id": zone_id,
                        "pets": pets,
                        "lucky_sigh": lucky_sigh,
                        "claimed_items": items,
                        "lottery_draws": draw_res
                    }
                    with self.db_lock:
                        self.db.save_account(update_result)
                    logger.info(f"{t_prefix}🎉 Hoàn tất thành công tài khoản '{username}'! Rút được {len(pets)} Pet: {', '.join(pets)} -> Đã lưu vào SQLite Database")
                    return update_result

                return {"username": username, "success": False, "status": status, "message": "Unknown status"}
            finally:
                _THREAD_LOG_CTX.prefix = ""

        # Distribute jobs across threads
        tasks = []
        for idx, acc in enumerate(pending, 1):
            worker_id = ((idx - 1) % num_workers) + 1
            tasks.append((idx, acc, worker_id))

        if num_workers > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                res_iter = executor.map(_process_single_pending, tasks)
                for res in res_iter:
                    if res:
                        results.append(res)
        else:
            for item in tasks:
                res = _process_single_pending(item)
                if res:
                    results.append(res)
                time.sleep(0.5)

        logger.info(f"\n🎉 Hoàn thành đợt chạy tiếp: {len([r for r in results if r.get('success')])}/{len(pending)} tài khoản thành công!")
        return results
    def export_results(self, results: list, filename: str = "accounts.txt"):
        """Summary logger (individual accounts are already exported in real time)"""
        successful = [r for r in results if r["success"]]
        if successful:
            logger.info(f"✅ Hoàn thành lưu trữ {len(successful)} tài khoản.")


    def sync_account_pets(self, target_username: str) -> tuple:
        """
        Connect to game server TCP socket for target_username, query complete pet inventory,
        and update SQLite database with authoritative list.
        Returns (success: bool, message: str, pets: list).
        """
        acc = self.db.get_account(target_username)
        if not acc:
            msg = f"Không tìm thấy tài khoản '{target_username}' trong Database"
            logger.error(f"❌ {msg}")
            return False, msg, []

        user_id = acc.get("user_id")
        token = acc.get("token")
        zone_id = acc.get("zone_id") or "4"
        if not user_id or not token:
            msg = f"Tài khoản '{target_username}' chưa có user_id hoặc token để kết nối socket"
            logger.error(f"❌ {msg}")
            return False, msg, []

        proxy_info = self.proxies[0] if self.proxies else None
        sock_client = GameSocketClient(proxy=proxy_info, timeout=10.0)

        logger.info(f"🔄 Đang kết nối Socket máy chủ để đồng bộ kho Pet cho '{target_username}' (Zone: {zone_id})...")
        try:
            lucky_info = {}
            pets = sock_client.query_account_pets(user_id=str(user_id), token=str(token), game_zone_id=str(zone_id), lucky_out=lucky_info)
            if pets is None:
                msg = "Không nhận được phản hồi danh sách Pet từ máy chủ game"
                return False, msg, []

            if lucky_info.get("lucky_sigh"):
                existing_acc = self.db.get_account(target_username)
                curr_lucky = existing_acc.get("lucky_sigh", "") if existing_acc else ""
                if lucky_info["lucky_sigh"] != "Đã rút" or not curr_lucky:
                    self.db.update_account_lucky_sigh(target_username, lucky_info["lucky_sigh"])

            new_entries = [p['entry'] for p in pets if p.get('entry')]

            # Nếu kho Pet trống (chưa rút hoặc vé còn kẹt trong thư), tự động nhận thư & ấp luôn!
            if not new_entries:
                logger.info(f"   ℹ️ Chưa thấy Pet trong kho, tự động kiểm tra hòm thư nhận vé & ấp trứng cho '{target_username}'...")
                succ, _, items, draw_res = sock_client.claim_mailbox(
                    user_id=str(user_id),
                    token=str(token),
                    game_zone_id=str(zone_id),
                    auto_draw=True
                )
                if draw_res:
                    if draw_res.get("lucky_sigh"):
                        self.db.update_account_lucky_sigh(target_username, draw_res["lucky_sigh"])
                    if draw_res.get("pets"):
                        new_entries = draw_res["pets"]
                        pets_str = ",".join(new_entries)
                        self.db.update_account_pets(target_username, pets_str)
                        msg = f"Đã nhận thư & ấp thành công {len(new_entries)} Pet từ Game Server!"
                        logger.info(f"🎉 {msg}: {', '.join(new_entries[:5])}")
                        return True, msg, [{"entry": e} for e in new_entries]

            pets_str = ",".join(new_entries)

            # Update database
            self.db.update_account_pets(target_username, pets_str)

            pet_names = [f"{p['name']} ({p.get('nature', {}).get('name', 'N/A')})" for p in pets]
            msg = f"Đã đồng bộ {len(pets)} Pet từ Game Server: {', '.join(pet_names[:5])}"
            logger.info(f"🎉 Hoàn tất đồng bộ '{target_username}': Có {len(pets)} Pet trong kho server! -> Đã cập nhật vào Database")
            return True, msg, pets
        except Exception as e:
            msg = f"Lỗi kết nối socket đồng bộ pet: {e}"
            logger.error(f"❌ {msg}")
            return False, msg, []

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Pokemon Auto Register Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test connection only
  python main.py --test
  
  # Dry run (no actual requests)
  python main.py --dry-run --count 3
  
  # Register 5 accounts to default server (Zone 1)
  python main.py --count 5
  
  # Register 5 accounts to Server 2
  python main.py --count 5 --zone 2
  
  # Register with custom delays
  python main.py --count 10 --delay-min 5 --delay-max 10

📚 Based on: ANALYSIS-poke-dai-chien.md
        """
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test API connection only'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no actual requests)'
    )
    
    parser.add_argument(
        '--visitor',
        action='store_true',
        help='Register as visitor account only without upgrading (userName="", accountType=0)'
    )

    parser.add_argument(
        '--normal',
        action='store_true',
        help='Direct registration without visitor upgrade (Note: visitor upgrade gets 20-ticket event reward)'
    )

    parser.add_argument(
        '--no-mail',
        action='store_true',
        help='Do not automatically claim mailbox rewards'
    )
    
    parser.add_argument(
        '--no-draw',
        action='store_true',
        help='Do not automatically execute 21-draw lottery (Ấp Cao Cấp)'
    )
    
    parser.add_argument(
        '--claim-user',
        type=str,
        default=None,
        help='Claim mailbox for existing account UID (requires --token and --zone)'
    )

    parser.add_argument(
        '--token',
        type=str,
        default=None,
        help='Token for --claim-user'
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=1,
        help='Number of accounts to create (default: 1)'
    )
    
    parser.add_argument(
        '--zone',
        type=str,
        default=DEFAULT_GAME_ZONE_ID,
        help=f'Game zone/server ID to bind to (default: {DEFAULT_GAME_ZONE_ID})'
    )
    
    parser.add_argument(
        '--delay-min',
        type=float,
        default=RATE_LIMIT["delay_min"],
        help=f'Minimum delay between requests (default: {RATE_LIMIT["delay_min"]}s)'
    )
    
    parser.add_argument(
        '--delay-max',
        type=float,
        default=RATE_LIMIT["delay_max"],
        help=f'Maximum delay between requests (default: {RATE_LIMIT["delay_max"]}s)'
    )
    
    parser.add_argument(
        '--max-per-minute', '--rpm',
        type=int,
        default=RATE_LIMIT["max_per_minute"],
        help=f'Maximum requests per minute limit (default: {RATE_LIMIT["max_per_minute"]})'
    )
    
    parser.add_argument(
        '--username',
        type=str,
        default=None,
        help='Fixed custom username (if omitted, random is generated)'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        default=None,
        help='Fixed custom password (if omitted, random is generated)'
    )

    parser.add_argument(
        '--no-increment',
        dest='auto_increment',
        action='store_false',
        default=True,
        help='Do not auto-increment custom username digits (default: auto-increment)'
    )

    parser.add_argument(
        '--threads',
        type=int,
        default=1,
        help='Number of concurrent worker threads (default: 1)'
    )

    parser.add_argument(
        '--proxy-file',
        type=str,
        default=None,
        help='Path to file containing proxies (one per line)'
    )

    parser.add_argument(
        '--proxy-type',
        type=str,
        default='socks5',
        choices=['http', 'https', 'socks5'],
        help='Default proxy protocol type (default: socks5)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Optional text file to export accounts to (default: saved directly to SQLite)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume pending accounts waiting for web reward or lottery draw'
    )

    parser.add_argument(
        '--sync-user',
        type=str,
        default='',
        help='Sync live pet warehouse directly from Game Server for a specific username'
    )

    parser.add_argument(
        '--refresh-servers',
        action='store_true',
        help='Fetch live servers from serverlist.php and update SQLite database'
    )
    parser.add_argument(
        '--resume-user',
        type=str,
        default='',
        help='Resume a specific pending username'
    )
    parser.add_argument(
        '--delete-users-file',
        type=str,
        default='',
        help='Delete usernames listed in a JSON file using native SQLite locking'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Fast path for safe native SQLite account deletion from GUI
    if args.delete_users_file:
        del_path = Path(args.delete_users_file)
        if not del_path.exists():
            print(json.dumps({"success": False, "error": "File not found"}), flush=True)
            sys.exit(1)
        try:
            with open(del_path, 'r', encoding='utf-8') as f:
                usernames_to_delete = json.load(f)
            if not isinstance(usernames_to_delete, list):
                print(json.dumps({"success": False, "error": "Invalid JSON list"}), flush=True)
                sys.exit(1)
            db_mgr = DatabaseManager()
            ok = db_mgr.delete_accounts(usernames_to_delete)
            print(f"DELETE_RESULT_JSON:{json.dumps({'success': ok, 'count': len(usernames_to_delete)})}", flush=True)
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}), flush=True)
            sys.exit(1)
    
    # Banner
    print("\n" + "="*60)
    print("🎮 Pokemon Auto Register Tool")
    print("="*60)
    print("⚠️  FOR EDUCATIONAL PURPOSES ONLY")
    print("📚 Based on: ANALYSIS-poke-dai-chien.md")
    print("="*60 + "\n")
    
    # Load Proxies if specified
    proxies = []
    if args.proxy_file:
        p_path = Path(args.proxy_file)
        if not p_path.is_absolute():
            if (Path.cwd() / args.proxy_file).exists():
                p_path = Path.cwd() / args.proxy_file
            elif getattr(sys, 'frozen', False):
                p_path = Path(sys.executable).resolve().parent / args.proxy_file
            else:
                p_path = Path(__file__).resolve().parent / args.proxy_file
        if p_path.exists():
            with open(p_path, 'r', encoding='utf-8') as f:
                for line in f:
                    p_obj = parse_proxy(line.strip(), default_type=args.proxy_type)
                    if p_obj:
                        proxies.append(p_obj)
            logger.info(f"🌐 Đã nạp {len(proxies)} proxy từ file '{p_path.name}'")
        else:
            logger.warning(f"⚠️ Không tìm thấy file proxy: {p_path}")

    # Create tool
    tool = AutoRegisterTool(
        dry_run=args.dry_run,
        default_zone=args.zone,
        max_per_minute=args.max_per_minute,
        threads=args.threads,
        proxies=proxies
    )
    
    # Test mode
    if args.test:
        logger.info("Running connection test...")
        success = tool.test_connection()
        sys.exit(0 if success else 1)
    
    # Standalone mailbox claim
    if args.claim_user:
        if not args.token:
            logger.error("❌ --claim-user requires --token")
            sys.exit(1)
        logger.info(f"📬 Connecting to claim mailbox for UID {args.claim_user} on Zone {args.zone}...")
        succ, msg, items, draw_res = tool.socket_client.claim_mailbox(
            user_id=args.claim_user,
            token=args.token,
            game_zone_id=args.zone,
            auto_draw=not args.no_draw
        )
        if succ:
            logger.info(f"✅ Mailbox & draw completed: {msg}")
            if draw_res.get("pets"):
                logger.info(f"🎉 Pet nhận được: {', '.join(draw_res['pets'])}")
            sys.exit(0)
        else:
            logger.error(f"❌ Failed to claim mailbox: {msg}")
            sys.exit(1)

        # Standalone pet synchronization
    if args.refresh_servers:
        from game_socket_client import fetch_and_save_live_servers
        live_map = fetch_and_save_live_servers()
        res_json = {
            "type": "refresh_servers_result",
            "success": len(live_map) > 0,
            "count": len(live_map)
        }
        print(f"REFRESH_SERVERS_JSON:{json.dumps(res_json)}", flush=True)
        sys.exit(0 if live_map else 1)

    if args.sync_user:
        target_u = args.sync_user.strip()
        succ, msg, pets = tool.sync_account_pets(target_username=target_u)
        result_json = {
            "type": "sync_result",
            "success": succ,
            "username": target_u,
            "message": msg,
            "pets": [p['entry'] for p in pets] if pets else [],
            "count": len(pets) if pets else 0
        }
        print(f"SYNC_RESULT_JSON:{json.dumps(result_json)}", flush=True)
        sys.exit(0 if succ else 1)

# Check if resume mode
    if args.resume or args.resume_user:
        target_u = args.resume_user.strip() if args.resume_user else None
        tool.resume_pending_accounts(target_username=target_u, auto_draw=not args.no_draw)
        return

    # Register accounts
    try:
        results = tool.register_batch(
            count=args.count,
            delay_range=(args.delay_min, args.delay_max),
            visitor_mode=args.visitor,
            visitor_upgrade=not args.normal,
            claim_mail=not args.no_mail,
            auto_draw=not args.no_draw,
            game_zone_id=args.zone,
            custom_username=args.username,
            custom_password=args.password,
            output_file=args.output,
            auto_increment=args.auto_increment
        )
        
        # Optional file export if specified on CLI
        if args.output and any(r["success"] for r in results):
            out_file = Path(args.output)
            tool.export_results(results, str(out_file))
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
