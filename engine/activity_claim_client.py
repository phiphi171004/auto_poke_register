"""
activity_claim_client.py
Client for Pokemon Web Activity Claim API
(https://activity.pocketgamesol.com)
Handles claiming web event rewards (e.g. 'Thưởng nâng cấp tk du khách' - 20 gold tickets)
Enhanced with thread-safety, safe JSON decoding, and character sync verification.
"""

import hashlib
import logging
import time
import threading
import requests
from typing import Optional, Dict, Tuple, List, Any

logger = logging.getLogger(__name__)

API_BASE = "https://activity.pocketgamesol.com"
APP_ID = "10062"
GROUP_ID = "5f682ae8b5cb673c9ca740ed"
ACT_ID = "5f682ae8b5cb673c9ca740ee"
REWARD_ID = "5f682ae8b5cb673c9ca740ef"

# Per-IP pacing state (prevents burst on a single IP while allowing 100% parallel execution across distinct proxies)
_IP_PACE_LOCK = threading.Lock()
_IP_NEXT_ALLOWED: Dict[str, float] = {}
_ZONE_CACHE_LOCK = threading.Lock()
_GLOBAL_ZONE_MAP_CACHE: Optional[Dict[str, int]] = None


def _pace_same_ip(ip_key: str, min_interval: float = 0.25) -> None:
    """Space out bursts from the exact same outgoing IP without blocking other proxies/threads."""
    wait_sec = 0.0
    with _IP_PACE_LOCK:
        now = time.monotonic()
        next_t = _IP_NEXT_ALLOWED.get(ip_key, 0.0)
        if now < next_t:
            wait_sec = next_t - now
            _IP_NEXT_ALLOWED[ip_key] = next_t + min_interval
        else:
            _IP_NEXT_ALLOWED[ip_key] = now + min_interval
    if wait_sec > 0:
        time.sleep(wait_sec)


class ActivityClaimClient:
    """Client for claiming web activity event rewards"""

    def __init__(self, timeout: float = 12.0, proxy: Optional[Dict] = None):
        self.proxy = proxy
        self.ip_key = f"{proxy.get('host')}:{proxy.get('port')}" if (proxy and proxy.get("host")) else "DIRECT"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://pokedaichien.pocketgamesol.com",
            "Referer": "https://pokedaichien.pocketgamesol.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if proxy and proxy.get("url"):
            self.session.proxies = {
                "http": proxy["url"],
                "https": proxy["url"]
            }
        self.timeout = timeout
        self._zone_map_cache: Optional[Dict[str, int]] = None

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _safe_get_json(self, url: str, params: Dict[str, Any], max_retries: int = 3, retry_delay: float = 1.2) -> Optional[Dict]:
        """
        Perform a safe GET request and parse JSON.
        Handles empty bodies, Nginx rate-limits, and temporary 502/503 errors gracefully.
        """
        for attempt in range(1, max_retries + 1):
            try:
                _pace_same_ip(self.ip_key, min_interval=0.25)
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    text = resp.text.strip() if resp.text else ""
                    if text:
                        try:
                            return resp.json()
                        except Exception:
                            pass
                elif resp.status_code in (502, 503, 504, 429):
                    logger.debug(f"Web server returned HTTP {resp.status_code}, retrying...")

                # Fallback to direct network connection if proxy caused failure
                if self.proxy and attempt == max_retries:
                    try:
                        _pace_same_ip("DIRECT", min_interval=0.25)
                        s_direct = requests.Session()
                        s_direct.headers.update(self.session.headers)
                        r_direct = s_direct.get(url, params=params, timeout=self.timeout)
                        if r_direct.status_code == 200 and r_direct.text and r_direct.text.strip():
                            return r_direct.json()
                    except Exception:
                        pass

            except Exception as e:
                logger.debug(f"Request attempt {attempt} to {url} failed: {e}")

            if attempt < max_retries:
                time.sleep(retry_delay)

        return None

    def login(self, username: str, plaintext_password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Login to activity web backend.
        Returns: (success, web_token, error_message)
        """
        hashed_pw = self._md5(plaintext_password)
        sign = self._md5(f"{username}{hashed_pw}v3_pokectgame_login")

        url = f"{API_BASE}/user/sdk/login"
        params = {
            "userName": username,
            "password": hashed_pw,
            "version": "v3",
            "sign": sign
        }

        data = self._safe_get_json(url, params=params, max_retries=3, retry_delay=1.5)
        if not data:
            return False, None, "Máy chủ Web không phản hồi dữ liệu đăng nhập (empty response hoặc mạng lag)"

        if data.get("code") == 200 and "state" in data and "token" in data["state"]:
            token = data["state"]["token"]
            return True, token, None
        else:
            err = str(data.get("state") or data.get("error_msg") or "Login failed")
            return False, None, err

    def get_zone_mapping(self, token: str) -> Dict[str, int]:
        """
        Fetch all zones and create a mapping from socket thirdGameZoneId (e.g. '4', '2160')
        to web activity gameZoneId (e.g. 8, 2064).
        """
        global _GLOBAL_ZONE_MAP_CACHE
        if self._zone_map_cache:
            return self._zone_map_cache
        with _ZONE_CACHE_LOCK:
            if _GLOBAL_ZONE_MAP_CACHE:
                self._zone_map_cache = _GLOBAL_ZONE_MAP_CACHE
                return self._zone_map_cache

        mapping: Dict[str, int] = {}
        url = f"{API_BASE}/user/sdk/zones"
        params = {"appId": APP_ID, "token": token}
        data = self._safe_get_json(url, params=params, max_retries=2, retry_delay=1.0)
        if data and data.get("code") == 200:
            for z in data.get("state", []):
                third_id = str(z.get("thirdGameZoneId", "")).strip()
                gz_id = int(z.get("gameZoneId", 0))
                if third_id:
                    mapping[third_id] = gz_id
            if mapping:
                self._zone_map_cache = mapping
                with _ZONE_CACHE_LOCK:
                    _GLOBAL_ZONE_MAP_CACHE = mapping

        # Standard fallback mappings
        if "4" not in mapping:
            mapping["4"] = 8
        if "2160" not in mapping:
            mapping["2160"] = 2064
        if "2162" not in mapping:
            mapping["2162"] = 2066
        return mapping

    def check_player(self, activity_zone_id: int, token: str) -> List[dict]:
        """Check if character exists on given activity zone"""
        url = f"{API_BASE}/user/player/list"
        params = {
            "appId": APP_ID,
            "gameZoneId": activity_zone_id,
            "token": token
        }
        data = self._safe_get_json(url, params=params, max_retries=2, retry_delay=0.8)
        if data and data.get("code") == 200:
            return data.get("state", [])
        return []

    def claim_event_reward(
        self,
        username: str,
        plaintext_password: str,
        socket_zone_id: str = "4"
    ) -> Tuple[bool, str]:
        """
        Execute full web activity claim reward flow (lock-free across distinct proxies):
        1. Login -> acquire web token
        2. Resolve web activity zone ID from socket zone ID
        3. Verify character exists on that zone (wait for game server sync)
        4. Call getUserReward to send 20 tickets straight into ingame mailbox
        Returns: (success, message)
        """
        logger.info(f"🎁 [Web Activity] Claiming 'Thưởng nâng cấp tk du khách' for {username}...")

        # 1. Login
        succ, token, err = self.login(username, plaintext_password)
        if not succ or not token:
            return False, f"Web login failed: {err}"

        # 2. Resolve activity zone ID
        zone_map = self.get_zone_mapping(token)
        sz_str = str(socket_zone_id).strip()
        act_zone_id = zone_map.get(sz_str)
        if not act_zone_id:
            if sz_str.isdigit():
                z_num = int(sz_str)
                # Pocket Games server rule: socket zone >= 2100 maps to web zone = socket zone - 96
                act_zone_id = (z_num - 96) if z_num >= 2100 else z_num
            else:
                act_zone_id = 8

        # 3. Check character with sync polling (wait up to 28s for game server to flush during high concurrency)
        players = []
        max_sync_polls = 16
        for poll_idx in range(1, max_sync_polls + 1):
            players = self.check_player(act_zone_id, token)
            if players:
                char_name = players[0].get('playerName', '')
                logger.info(f"   👤 Đã đồng bộ nhân vật '{char_name}' trên máy chủ web (Lần {poll_idx}).")
                break
            sleep_duration = 1.2 if poll_idx <= 4 else (1.8 if poll_idx <= 10 else 2.2)
            time.sleep(sleep_duration)

        if not players:
            logger.warning(f"   ⚠️ Chưa tìm thấy nhân vật trên Web sau 28s. Tránh gửi quà rỗng để không bị lỗi service.")
            return False, "Nhân vật đang được máy chủ đồng bộ dồn tải. Vui lòng bấm nút 'Tiếp tục nhận vé' sau vài giây để nhận lại."

        # 4. Check if already claimed
        url_check = f"{API_BASE}/activity/getUserReward"
        params_check = {
            "groupId": GROUP_ID,
            "actId": ACT_ID,
            "token": token
        }
        c_data = self._safe_get_json(url_check, params=params_check, max_retries=2, retry_delay=1.0)
        if c_data and c_data.get("code") == 200 and c_data.get("state") and len(c_data["state"]) > 0:
            logger.info("   ℹ️ Quà 'Thưởng nâng cấp tk du khách' đã được nhận trước đó.")
            return True, "Already claimed"

        # 5. Claim reward with retry loop
        url_claim = f"{API_BASE}/activity/getUserReward"
        params_claim = {
            "groupId": GROUP_ID,
            "actId": ACT_ID,
            "token": token,
            "rewardId": REWARD_ID
        }

        for attempt in range(1, 5):
            claim_json = self._safe_get_json(url_claim, params=params_claim, max_retries=2, retry_delay=1.2)
            if not claim_json:
                if attempt < 4:
                    time.sleep(1.5)
                    continue
                return False, "Máy chủ quà tặng không phản hồi JSON sau nhiều lần thử"

            code = claim_json.get("code")
            if code == 200:
                reward_name = claim_json.get("state", {}).get("rewardName", "Thưởng nâng cấp tk du khách")
                logger.info(f"   🎉 Nhận web reward thành công: '{reward_name}'! Quà đã gửi vào hòm thư ingame.")
                return True, f"Claimed '{reward_name}' successfully"
            elif code == 1005:
                logger.info("   ℹ️ Quà đã được nhận trước đó (code 1005).")
                return True, "Already claimed (1005)"
            else:
                msg = str(claim_json.get("state") or claim_json.get("msg") or "Unknown claim error")
                if attempt < 4:
                    logger.info(f"   ℹ️ Lần {attempt}/4 nhận web reward ({msg}), đang thử lại sau 2.0s...")
                    time.sleep(2.0)
                    continue
                else:
                    logger.warning(f"   ⚠️ Nhận web reward chưa thành công sau 4 lần thử: {msg}")
                    return False, msg

        return False, "Không thể nhận web reward sau 4 lần thử"
