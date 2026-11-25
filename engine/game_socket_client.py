"""
game_socket_client.py
Game Server Socket TCP Client for Pokemon (libHOGame protocol)
Handles Stage 3: Web Backend Session Activation + Socket Login + Create Avatar (Role Name)
"""

import sys
import re
import socket
import struct
import json
import hashlib
import requests
import logging
import zlib
import time
import random
from pathlib import Path
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# Game Web Backend Configuration
GAME_WEB_BASE = "http://vn-login.pokedaichien.pocketgamesol.com"
GAME_WEB_SALT = "c3ceea433f91b01590618fcfecdc9446"

# Known server map fallback (server_id -> (host, port))
DEFAULT_SERVER_MAP: Dict[str, Tuple[str, int]] = {
    "1": ("125.212.215.105", 20001),  # Poke S1
    "2": ("125.212.214.2", 20002),    # Poke S2
    "3": ("125.212.214.2", 20002),    # Poke S3
    "4": ("125.212.214.2", 20002),    # Poke S4
    "5": ("125.212.214.2", 20002),    # Poke S5
    "6": ("125.212.214.2", 20006),    # Poke S6
    "2160": ("125.212.214.184", 22160), # Poke S1960 (Newest active server)
}

# Dynamic server map with all 1960+ servers (loaded from SQLite)
DYNAMIC_SERVER_MAP: Dict[str, Tuple[str, int]] = dict(DEFAULT_SERVER_MAP)
try:
    import os
    _db_path = None
    _env_db = os.environ.get("POKEMON_DB_PATH")
    if _env_db and Path(_env_db).exists():
        _db_path = Path(_env_db)

    if not _db_path:
        _file_dir = Path(__file__).resolve().parent
        _candidates = [
            _file_dir.parent / "data" / "pokemon_web.db",
            _file_dir.parent / "pokemon_data.db",
            Path.cwd() / "data" / "pokemon_web.db",
        ]
        for _c in _candidates:
            if _c.exists():
                _db_path = _c
                break

    if _db_path and _db_path.exists():
        import sqlite3
        with sqlite3.connect(str(_db_path), timeout=5.0) as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT id, tcp FROM servers")
            for _row in _cur.fetchall():
                _sid = str(_row[0])
                _tcp = str(_row[1])
                if ":" in _tcp:
                    _h, _p = _tcp.split(":")
                    DYNAMIC_SERVER_MAP[_sid] = (_h, int(_p))
except Exception:
    pass

DEFAULT_HOST = "125.212.214.2"
DEFAULT_PORT = 20002


def game_urlencode(s: str) -> str:
    """
    Game Engine strict URL encoder.
    Every non-alphanumeric character is converted to %XX.
    Matches libHOGame.so byte-for-byte.
    """
    res = []
    for ch in s:
        if ch.isalnum():
            res.append(ch)
        else:
            res.append(f"%{ord(ch):02X}")
    return "".join(res)


def fetch_and_save_live_servers() -> Dict[str, Tuple[str, int]]:
    """
    Fetch all live servers from Pocket Games official serverlist.php API,
    persist newly discovered servers into SQLite, and update DYNAMIC_SERVER_MAP.
    """
    import urllib.parse
    import hashlib
    import json
    import requests
    from db_manager import find_db_path

    salt = 'D#L!S@O#*!'
    req_obj = [{'func': 'GetServerList', 'userid': 'yuenan#1'}]
    req_json = json.dumps(req_obj, separators=(',', ':'))
    seq = 4
    sig = hashlib.md5(f'{seq}{req_json}{salt}'.encode('utf-8')).hexdigest()
    encoded_req = urllib.parse.quote(req_json)
    post_data = f'bv=70%2E0%2E0&ptype=a&request={encoded_req}&seq={seq}&session=&sig={sig}&sptype=spyuenan%5Fmd&version=73%2E0%2E0'

    url = f"{GAME_WEB_BASE}/serverlist/serverlist.php"
    res_map = {}
    try:
        resp = requests.post(
            url,
            data=post_data.encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Dalvik/2.1.0'},
            timeout=8.0
        )
        if resp.status_code == 200:
            text = resp.text
            if text.startswith('0;'):
                text = text[2:]
            data = json.loads(text)
            infos = data[0].get('infos', []) if data and len(data) > 0 else []

            db_p = find_db_path()
            to_db = []
            for s in infos:
                sid = str(s.get('id', '')).strip()
                sname = str(s.get('name', '')).strip()
                tcp_str = str(s.get('tcp', '')).strip()
                if tcp_str.startswith('/'):
                    tcp_str = tcp_str[1:]
                if sid and tcp_str and ':' in tcp_str:
                    h, p = tcp_str.split(':', 1)
                    parsed_pair = (h.strip(), int(p.strip()))
                    DYNAMIC_SERVER_MAP[sid] = parsed_pair
                    res_map[sid] = parsed_pair
                    to_db.append((sid, sname, tcp_str, 'online'))

            if db_p and db_p.exists() and to_db:
                import sqlite3
                with sqlite3.connect(str(db_p), timeout=5.0) as conn:
                    cur = conn.cursor()
                    cur.executemany("""
                        INSERT INTO servers (id, name, tcp, status)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,
                            tcp=excluded.tcp,
                            status=excluded.status,
                            updated_at=CURRENT_TIMESTAMP
                    """, to_db)
                    conn.commit()
            logger.info(f"🌐 Đã tự động cập nhật {len(infos)} máy chủ trực tuyến từ Game Server!")
    except Exception as e:
        logger.debug(f"fetch_and_save_live_servers error: {e}")

    return res_map


class GameSocketClient:
    """Client communicating with Game Web Backend and Game Server TCP Socket"""

    def __init__(self, timeout: float = 12.0, proxy: Optional[Dict] = None, device_telemetry: Optional[Dict] = None):
        self.timeout = timeout
        self.proxy = proxy
        self.device_telemetry = device_telemetry or {}
        self.model = self.device_telemetry.get("model") or "SM-S928B"
        self.os_version = str(self.device_telemetry.get("osVersion") or "14")
        self.mac = self.device_telemetry.get("mac") or ""
        self.session = requests.Session()
        self.session.headers.update({
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": f"Dalvik/2.1.0 (Linux; U; Android {self.os_version}; {self.model} Build/PQ3A.190605.09022056)",
            "Host": "vn-login.pokedaichien.pocketgamesol.com",
            "Accept-Encoding": "gzip"
        })
        if proxy and proxy.get("url"):
            self.session.proxies = {
                "http": proxy["url"],
                "https": proxy["url"]
            }

    def _create_socket(self, force_direct: bool = False) -> socket.socket:
        if self.proxy and not force_direct:
            try:
                import socks
                ptype = socks.SOCKS5 if self.proxy.get("type") == "socks5" else socks.HTTP
                s = socks.socksocket()
                s.set_proxy(
                    proxy_type=ptype,
                    addr=self.proxy["host"],
                    port=self.proxy["port"],
                    username=self.proxy.get("username"),
                    password=self.proxy.get("password")
                )
                return s
            except Exception as e:
                logger.warning(f"⚠️ Không thể tạo proxy socket ({e}), dùng direct socket")
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    @staticmethod
    def _is_proxy_dead_error(err: BaseException) -> bool:
        """
        Return True ONLY when the local/remote Proxy itself failed to accept or establish a tunnel
        (e.g. PySocks ProxyError, WinError 10061 refused on proxy port).
        Return False when the tunnel reached the Game Server and the Game Server closed/reset it
        (0-byte handshake, WinError 10054/10053, LoginResult timeout), so threads stay on their
        assigned proxy IPs instead of stampeding onto the host machine's single WAN IP.
        """
        cls_name = type(err).__name__.lower()
        if "proxy" in cls_name or "socks" in cls_name:
            return True
        msg = str(err).lower()
        if any(k in msg for k in (
            "proxyerror",
            "generalproxyerror",
            "http proxy",
            "socks",
            "10061",
            "actively refused",
            "unable to connect to proxy"
        )):
            return True
        return False

    @staticmethod
    def _recv_handshake(sock: socket.socket) -> bytes:
        """
        Dynamically receive Handshake response without hardcoded length.
        Server sends Chunk 1 (Greeting JSON, length in header[5:7]) + Chunk 2 (16-byte ACK 0x0b).
        Total expected bytes = pkt1_len + 16.
        """
        hs = b""
        expected_len = 0
        for _ in range(25):
            chunk = sock.recv(1024)
            if not chunk:
                break
            hs += chunk
            if expected_len == 0 and len(hs) >= 7:
                pkt1_len = (hs[5] << 8) | hs[6]
                expected_len = pkt1_len + 16
            if expected_len > 0 and len(hs) >= expected_len:
                break
        return hs

    @staticmethod
    def resolve_server(game_zone_id: str) -> Tuple[str, int]:
        """Resolve IP and Port for given game zone / server ID"""
        zone_str = str(game_zone_id).strip()
        if zone_str in DYNAMIC_SERVER_MAP:
            return DYNAMIC_SERVER_MAP[zone_str]

        # On-demand lookup from SQLite for newly added servers
        try:
            from db_manager import find_db_path
            db_p = find_db_path()
            if db_p and db_p.exists():
                import sqlite3
                with sqlite3.connect(str(db_p), timeout=3.0) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT tcp FROM servers WHERE id = ?", (zone_str,))
                    row = cur.fetchone()
                    if row and ":" in str(row[0]):
                        clean_tcp = str(row[0]).strip()
                        if clean_tcp.startswith("/"):
                            clean_tcp = clean_tcp[1:]
                        h, p = clean_tcp.split(":", 1)
                        res = (h.strip(), int(p.strip()))
                        DYNAMIC_SERVER_MAP[zone_str] = res
                        return res
        except Exception:
            pass

        # If server not in local DB (e.g. brand new server just released), fetch live from serverlist.php!
        try:
            live_map = fetch_and_save_live_servers()
            if zone_str in live_map:
                return live_map[zone_str]
        except Exception:
            pass

        return (DEFAULT_HOST, DEFAULT_PORT)

    @staticmethod
    def _compute_checksum(header_12: bytes, body: bytes) -> bytes:
        """
        Compute dual 16-bit CRC checksum matching libHOGame.so SJ::Net::Message::encode byte-for-byte.
        Returns 4 bytes: CRC2 (2 bytes) + CRC1 (2 bytes).
        """
        pkt_rest = header_12 + body
        crc1 = zlib.crc32(pkt_rest) & 0xffff
        crc1_bytes = struct.pack('>H', crc1)
        header_14 = crc1_bytes + header_12
        crc2 = zlib.crc32(header_14) & 0xffff
        crc2_bytes = struct.pack('>H', crc2)
        return crc2_bytes + crc1_bytes

    @classmethod
    def _pack_packet(cls, seq_num: int, form_body: bytes = b'', opcode: int = 0) -> bytes:
        """
        Build the 16-byte binary header + URL-encoded body
        Header format:
          0..2  : 2 bytes CRC2 (checksum of header_14: crc1_bytes + header_12)
          2..4  : 2 bytes CRC1 (checksum of pkt_rest: header_12 + form_body)
          4..8  : 4 bytes length [00, (len >> 8) & ff, len & ff, opcode]
          8..16 : 8 bytes sequence number (big-endian unsigned long long)
        """
        total_len = 16 + len(form_body)
        len_field = bytes([0, (total_len >> 8) & 0xff, total_len & 0xff, opcode])
        seq_field = struct.pack('>Q', seq_num)
        header_12 = len_field + seq_field
        chk = cls._compute_checksum(header_12, form_body)
        return chk + header_12 + form_body

    @staticmethod
    def _decode_frame_payload(opcode: int, payload: bytes) -> bytes:
        """
        Decode a single libHOGame frame payload (bytes after the 16-byte header).
        - opcode == 0x01 (or zlib header 0x78): zlib-compressed UTF-8 JSON ('0;[...]')
        - opcode == 0x00: plain UTF-8 JSON ('0;[...]')
        """
        if not payload:
            return b""
        if opcode == 0x01 or payload[0] == 0x78:
            try:
                return zlib.decompress(payload)
            except Exception:
                for off in range(1, min(8, len(payload))):
                    if payload[off] == 0x78:
                        try:
                            return zlib.decompress(payload[off:])
                        except Exception:
                            pass
        return payload

    @staticmethod
    def _extract_func_object(resp_text: str, func_name: str) -> Optional[dict]:
        """
        Parse libHOGame S2C payloads ('<ret>;[{...}, ...]') identically to
        proto::UnrealS2C::OnData (0x016509fc in libHOGame.so):
        decodes each top-level JSON array via JSONDecoder.raw_decode and returns
        the dict whose 'func' == func_name, regardless of JSON key order or nested
        arrays (such as 'mails' / 'items' appearing before 'func').
        """
        if not resp_text or func_name not in resp_text:
            return None

        decoder = json.JSONDecoder()
        for line in resp_text.splitlines():
            if func_name not in line:
                continue
            pos = 0
            n = len(line)
            while pos < n:
                br_pos = line.find("[", pos)
                if br_pos == -1:
                    break
                try:
                    parsed, end_pos = decoder.raw_decode(line, br_pos)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and item.get("func") == func_name:
                                return item
                    pos = max(end_pos, br_pos + 1)
                except Exception:
                    pos = br_pos + 1
        return None

    @classmethod
    def _recv_all(
        cls,
        sock: socket.socket,
        target_keyword: Optional[str] = None,
        max_tries: int = 15,
        raise_on_error: bool = False,
        timeout_sec: Optional[float] = None
    ) -> bytes:
        """
        Receive and reassemble libHOGame TCP frames using exact 24-bit frame_len
        (header[4..7]) + wall-clock deadline (never counting arbitrary TCP recv chunks).
        - Transparently skips 16-byte ACK frames (frame_len == 16).
        - Transparently decompresses opcode == 0x01 zlib frames (e.g. X10 draws, QueryPetList).
        - Guarantees complete frame alignment even across dozens of fragmented TCP segments.
        """
        orig_timeout = None
        try:
            orig_timeout = sock.gettimeout()
        except Exception:
            pass

        if timeout_sec is not None:
            total_timeout = float(timeout_sec)
        elif max_tries <= 2 and not raise_on_error:
            total_timeout = 1.8
        else:
            base_to = float(orig_timeout) if (orig_timeout and orig_timeout > 0) else 10.0
            total_timeout = max(8.0, min(15.0, base_to))

        deadline = time.monotonic() + total_timeout
        raw_buf = bytearray()
        parse_offset = 0
        decoded_parts = []
        kw_bytes = target_keyword.encode('utf-8') if target_keyword else None

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                try:
                    sock.settimeout(max(0.05, remaining))
                except Exception:
                    pass

                try:
                    chunk = sock.recv(8192)
                    if not chunk:
                        joined_now = b"\n".join(decoded_parts)
                        if raise_on_error and (not kw_bytes or kw_bytes not in joined_now):
                            raise socket.error("Socket closed by remote host before response (EOF)")
                        break

                    raw_buf.extend(chunk)

                    # Reassemble all complete 16-byte-headed libHOGame frames in raw_buf
                    while len(raw_buf) - parse_offset >= 16:
                        frame_len = (
                            (raw_buf[parse_offset + 4] << 16)
                            | (raw_buf[parse_offset + 5] << 8)
                            | raw_buf[parse_offset + 6]
                        )
                        opcode = raw_buf[parse_offset + 7]

                        # Fallback only for synthetic/unframed mock test streams
                        if frame_len < 16 or frame_len > 2 * 1024 * 1024:
                            rem = bytes(raw_buf[parse_offset:])
                            decoded_parts.append(cls._decode_frame_payload(0, rem))
                            parse_offset = len(raw_buf)
                            break

                        # Frame still fragmented across TCP segments -> keep reading recv()!
                        if len(raw_buf) - parse_offset < frame_len:
                            break

                        if frame_len > 16:
                            payload = bytes(raw_buf[parse_offset + 16 : parse_offset + frame_len])
                            decoded = cls._decode_frame_payload(opcode, payload)
                            if decoded:
                                decoded_parts.append(decoded)
                        parse_offset += frame_len

                    has_partial_frame = (parse_offset < len(raw_buf))
                    if not has_partial_frame and decoded_parts:
                        joined = b"\n".join(decoded_parts)
                        if kw_bytes:
                            if kw_bytes in joined:
                                break
                        elif b';[' in joined or b'{"' in joined:
                            break

                except socket.timeout:
                    joined_now = b"\n".join(decoded_parts)
                    if kw_bytes and kw_bytes in joined_now and parse_offset == len(raw_buf):
                        break
                    if not kw_bytes and decoded_parts and parse_offset == len(raw_buf):
                        break
                except (socket.error, OSError) as e:
                    logger.debug(f"recv socket error: {e}")
                    joined_now = b"\n".join(decoded_parts)
                    if raise_on_error and (not kw_bytes or kw_bytes not in joined_now):
                        raise
                    break
                except Exception as e:
                    logger.debug(f"recv error: {e}")
                    joined_now = b"\n".join(decoded_parts)
                    if raise_on_error and (not kw_bytes or kw_bytes not in joined_now):
                        raise socket.error(str(e))
                    break
        finally:
            if orig_timeout is not None:
                try:
                    sock.settimeout(orig_timeout)
                except Exception:
                    pass

        # Salvage any trailing unparsed payload if connection closed mid-stream
        if parse_offset < len(raw_buf) and len(raw_buf) - parse_offset > 16:
            opcode = raw_buf[parse_offset + 7]
            tail = cls._decode_frame_payload(opcode, bytes(raw_buf[parse_offset + 16:]))
            if tail:
                decoded_parts.append(tail)

        result_bytes = b"\n".join(decoded_parts)
        if raise_on_error and kw_bytes and kw_bytes not in result_bytes:
            raise socket.timeout(f"Timed out waiting for '{target_keyword}' from server")
        return result_bytes

    def activate_web_session(
        self,
        user_id: str,
        token: str,
        device_model: Optional[str] = None
    ) -> bool:
        """
        Activate user session on game web backend (GetSpUserInfo)
        This authorizes the account to open the TCP Game Socket.
        """
        m = device_model or self.model
        dev_info = json.dumps({
            "DeviceInfo": {
                "extra": "",
                "mac": self.mac,
                "model": m,
                "os": "Android",
                "osversion": self.os_version
            }
        }, separators=(',', ':'))

        req_obj = [{
            "deviceinfo": dev_info,
            "func": "GetSpUserInfo",
            "session": token,
            "uid": str(user_id)
        }]
        req_json = json.dumps(req_obj, separators=(',', ':'))
        seq = 0
        sig = hashlib.md5(f"{seq}{req_json}{GAME_WEB_SALT}".encode('utf-8')).hexdigest()

        body = (
            f"bv=70%2E0%2E0&ptype=a&request={game_urlencode(req_json)}"
            f"&seq={seq}&session=&sig={sig}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
        )
        url = f"{GAME_WEB_BASE}/sdk/yuenan_md/userinfo.php"

        try:
            resp = self.session.post(url, data=body.encode('utf-8'), timeout=8.0)
            if resp.status_code == 200 and "GetSpUserInfoResult" in resp.text:
                logger.info(f"🌐 Web backend session activated for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Web session activation failed: {resp.text}")
                return False
        except Exception as e:
            # Smart fallback: If proxy died or refused connection (e.g. WinError 10061 / Timeout), retry via direct
            err_msg = str(e)
            if self.proxy and ("ProxyError" in err_msg or "10061" in err_msg or "refused" in err_msg.lower() or "timeout" in err_msg.lower()):
                logger.warning(f"   ⚠️ Proxy {self.proxy.get('host')}:{self.proxy.get('port')} không phản hồi, thử kích hoạt session web qua mạng trực tiếp...")
                try:
                    direct_s = requests.Session()
                    direct_s.headers.update(self.session.headers)
                    d_resp = direct_s.post(url, data=body.encode('utf-8'), timeout=8.0)
                    if d_resp.status_code == 200 and "GetSpUserInfoResult" in d_resp.text:
                        logger.info(f"🌐 Web backend session activated for user {user_id} (qua mạng trực tiếp)")
                        return True
                except Exception as de:
                    logger.warning(f"⚠️ Kích hoạt qua mạng trực tiếp thất bại: {de}")
            logger.warning(f"⚠️ Error activating web session: {e}")
            return False

    def _fetch_server_list(self, user_id: str) -> bool:
        """
        Notify web backend of serverlist query (matches official game client flow)
        """
        try:
            req_obj = [{
                "func": "GetServerList",
                "userid": f"yuenan#{user_id}"
            }]
            req_json = json.dumps(req_obj, separators=(',', ':'))
            seq = 4
            sig = hashlib.md5(f"{seq}{req_json}{GAME_WEB_SALT}".encode('utf-8')).hexdigest()
            body = (
                f"bv=70%2E0%2E0&ptype=a&request={game_urlencode(req_json)}"
                f"&seq={seq}&session=&sig={sig}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            )
            url = f"{GAME_WEB_BASE}/serverlist/serverlist.php"
            resp = self.session.post(url, data=body.encode('utf-8'), timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _check_account_level(self, user_id: str) -> bool:
        """
        Check account level via checkAccountLvUP.php (GetUseraccountInfo)
        This may be required before socket login is allowed.
        Includes smart backoff retry for rotating proxies (3-5s switch gap) & direct fallback.
        """
        import time
        session_timestamp = str(int(time.time()))

        req_obj = [{
            "func": "GetUseraccountInfo",
            "session": session_timestamp,
            "uid": str(user_id)
        }]
        req_json = json.dumps(req_obj, separators=(',', ':'))
        seq = 5
        sig = hashlib.md5(f"{seq}{req_json}{GAME_WEB_SALT}".encode('utf-8')).hexdigest()

        body = (
            f"bv=70%2E0%2E0&ptype=a&request={game_urlencode(req_json)}"
            f"&seq={seq}&session=&sig={sig}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
        )
        url = f"{GAME_WEB_BASE}/sdk/yuenan_md/checkAccountLvUP.php"

        max_http_tries = 2
        for attempt in range(1, max_http_tries + 1):
            try:
                resp = self.session.post(url, data=body.encode('utf-8'), timeout=10.0)
                if resp.status_code == 200:
                    logger.info(f"✅ Account level checked for user {user_id}")
                    return True
                else:
                    logger.warning(f"⚠️ Account level check returned status {resp.status_code}: {resp.text[:80]}")
                    return False
            except Exception as e:
                err_msg = str(e)
                is_proxy_gap = self.proxy and any(
                    k in err_msg.lower() for k in ("timeout", "timed out", "10061", "10054", "proxyerror", "refused", "reset")
                )
                if attempt < max_http_tries and is_proxy_gap:
                    # Proxy LAN đang xoay IP hoặc nghẽn, đợi 3.8s để có IP mới rồi thử lại
                    time.sleep(3.8 + random.uniform(0.0, 0.4))
                    continue

                # Nếu thử lại qua proxy vẫn lỗi hoặc cổng proxy sập hẳn -> fallback qua direct
                if is_proxy_gap:
                    try:
                        direct_s = requests.Session()
                        direct_s.headers.update(self.session.headers)
                        d_resp = direct_s.post(url, data=body.encode('utf-8'), timeout=10.0)
                        if d_resp.status_code == 200:
                            logger.info(f"✅ Account level checked for user {user_id} (qua mạng trực tiếp)")
                            return True
                    except Exception:
                        pass

                logger.warning(f"⚠️ Error checking account level: {e}")
                return False
        return False

    def create_character(
        self,
        user_id: str,
        character_name: str,
        game_zone_id: str = "4",
        chief_buddy: int = 1002,
        gender: int = 0,
        device_id: Optional[str] = None,
        token: Optional[str] = None,
        claim_mail: bool = True
    ) -> Tuple[bool, str]:
        """
        Execute Stage 3:
          1. Activate web session if token provided
          2. Connect to Game Server TCP Socket
          3. Perform Handshake
          4. Login to Game Server -> Obtain session_key
          5. Send QueryAvatarAttribute / QueryChargeInfo
          6. Send CreateAvatar -> Verify character creation
        """
        # Step 1: Web backend activation if token is available
        if token:
            self.activate_web_session(user_id=user_id, token=token)
            self._fetch_server_list(user_id=user_id)
            self._check_account_level(user_id=user_id)

        host, port = self.resolve_server(game_zone_id)
        zone_int = int(game_zone_id) if str(game_zone_id).isdigit() else 4
        if not device_id or device_id.strip() in ("DEVICE#", "DEVICE", ""):
            dev_hash = hashlib.md5(f"DEV_{user_id}".encode()).hexdigest()[:32]
            dev_id = f"DEVICE#{dev_hash}"
        else:
            dev_id = device_id
        
        logger.info(f"[DEBUG] dev_id = {dev_id}")
        
        max_retries = 4
        last_error = "Unknown socket error"
        proxy_dead = False
        # Dải thời gian nghỉ thích ứng proxy xoay IP (mất 3-5s để có IP mới)
        backoff_steps = (3.5, 4.5, 5.5)
        
        for attempt in range(1, max_retries + 1):
            use_direct = (proxy_dead and self.proxy is not None)
            if use_direct:
                logger.warning("   ⚠️ Cổng Proxy không phản hồi, chuyển sang kết nối socket trực tiếp...")
            sock = self._create_socket(force_direct=use_direct)
            sock.settimeout(self.timeout)
            active_sock = sock

            try:
                if attempt > 1:
                    logger.info(f"🔄 Đang kết nối lại Game Server socket (Lần {attempt}/{max_retries}) tại {host}:{port}...")
                else:
                    logger.info(f"🔌 Stage 3: Connecting to Game Server socket at {host}:{port} (Zone: {game_zone_id})...")
                
                sock.connect((host, port))

                # ── 1. Handshake ─────────────────────────────────────────────
                handshake = self._pack_packet(seq_num=5, form_body=b'', opcode=0x0a)
                sock.sendall(handshake)
                hs_total = self._recv_handshake(sock)

                logger.info(f"[DEBUG] Handshake fully received ({len(hs_total)} bytes)")
                if len(hs_total) < 16:
                    raise socket.error("Server closed connection during initial handshake")

                # ── 2. Login to Game Server ──────────────────────────────────
                device_info = {
                    "appVersion": "73.0.0",
                    "appBaseVersion": "70.0.0",
                    "deviceId": dev_id,
                    "combinedDeviceId": "_",
                    "deviceCheckChannel": "",
                    "deviceType": 17,
                    "model": self.model,
                    "os": "Android",
                    "osversion": self.os_version,
                    "mac": self.mac
                }
                device_info_str = json.dumps(device_info, separators=(',', ':'))

                login_request_json = json.dumps([{
                    "deviceType": 2,
                    "func": "Login",
                    "info": device_info_str,
                    "serverid": zone_int,
                    "userid": f"yuenan#{user_id}"
                }], separators=(',', ':'))

                login_body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(login_request_json)}"
                    f"&seq=1&session=&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')

                login_pkt = self._pack_packet(seq_num=0, form_body=login_body, opcode=0)
                sock.sendall(login_pkt)

                login_resp_data = self._recv_all(sock, target_keyword="LoginResult", max_tries=15)
                login_text = login_resp_data.decode('utf-8', errors='ignore')

                if "LoginResult" not in login_text:
                    raise socket.error(f"Failed to login on socket: {login_text or 'empty'}")

                login_obj = self._extract_func_object(login_text, "LoginResult")
                session_key = login_obj.get("session_key") if login_obj else None
                if not session_key:
                    m_sk = re.search(r'"session_key"\s*:\s*"([A-Za-z0-9_]+)"', login_text)
                    if m_sk:
                        session_key = m_sk.group(1)

                if not session_key:
                    return False, f"Invalid login result format: {login_text[:100]}"

                logger.info(f"🔑 Session key acquired: {session_key}")

                # ── 3. Client ACK + State Sync ──────────────────────────────
                ack_pkt = self._pack_packet(seq_num=1, form_body=b'', opcode=0x14)
                sock.sendall(ack_pkt)

                # QueryAvatarAttribute (seq=2)
                q_req = json.dumps([{"func": "QueryAvatarAttribute"}], separators=(',', ':'))
                q_body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(q_req)}"
                    f"&seq=2&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')
                sock.sendall(self._pack_packet(seq_num=2, form_body=q_body, opcode=0))

                # QueryChargeInfo (seq=3)
                c_req = json.dumps([{"func": "QueryChargeInfo"}], separators=(',', ':'))
                c_body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(c_req)}"
                    f"&seq=3&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')
                sock.sendall(self._pack_packet(seq_num=3, form_body=c_body, opcode=0))

                # ── 4. CreateAvatar (Set Character Name, seq=4) ─────────────
                create_request_json = json.dumps([{
                    "avatarName": character_name,
                    "chiefBuddy": chief_buddy,
                    "func": "CreateAvatar",
                    "gender": gender
                }], separators=(',', ':'))

                create_body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(create_request_json)}"
                    f"&seq=4&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')

                create_pkt = self._pack_packet(seq_num=4, form_body=create_body, opcode=0)
                sock.sendall(create_pkt)
                logger.info(f"📤 Sent CreateAvatar packet for '{character_name}'...")

                # Receive CreateAvatar Response
                create_resp_data = self._recv_all(sock, target_keyword="CreateAvatarResult", max_tries=15)
                create_text = create_resp_data.decode('utf-8', errors='ignore')

                if "CreateAvatarResult" in create_text:
                    try:
                        create_obj = self._extract_func_object(create_text, "CreateAvatarResult")
                        if create_obj is None:
                            raise ValueError(f"Missing CreateAvatarResult object in: {create_text[:120]}")
                        error_code = create_obj.get("error_code", -1)
                        if error_code == 0:
                            logger.info(f"✨ Character '{character_name}' created successfully on Zone {game_zone_id}!")
                            
                            # Send QueryAvatarAttribute (seq=5) to enter the world & commit character to server DB
                            try:
                                qa_req = json.dumps([{"func": "QueryAvatarAttribute"}], separators=(',', ':'))
                                qa_body = (
                                    f"bv=70%2E0%2E0&request={game_urlencode(qa_req)}"
                                    f"&seq=5&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                                ).encode('utf-8')
                                sock.sendall(self._pack_packet(seq_num=5, form_body=qa_body, opcode=0))
                                self._recv_all(sock, target_keyword="QueryAvatarAttributeResult", max_tries=8)
                                logger.info(f"   👤 Đã đồng bộ nhân vật vào thế giới game trên máy chủ!")
                                time.sleep(0.5)
                            except Exception as e_sync:
                                logger.warning(f"   ⚠️ Lỗi đồng bộ QueryAvatarAttribute sau tạo nv: {e_sync}")

                            # Step 5: Automatically Claim Mailbox
                            if claim_mail:
                                logger.info("📬 Checking and claiming mailbox rewards...")
                                self._claim_mailbox_stream(sock, session_key, start_seq=6)
                            
                            return True, f"Role '{character_name}' created successfully (error_code: 0)"
                        else:
                            return False, f"Server returned CreateAvatar error_code: {error_code}"
                    except Exception as e:
                        return False, f"Failed to parse CreateAvatarResult: {e}"

                if "QueryAvatarAttributeResult" in create_text:
                    return True, f"Role verified on server ({character_name})"

                return False, f"Unexpected response from CreateAvatar: {create_text or 'empty'}"

            except (socket.error, ConnectionResetError, socket.timeout) as e:
                last_error = f"Socket error: {e}"
                if self.proxy is not None and self._is_proxy_dead_error(e):
                    proxy_dead = True
                if attempt < max_retries:
                    logger.info(f"   ℹ️ Kết nối socket lần {attempt}/{max_retries} gián đoạn ({e}), đang thử lại...")
                    wait_s = backoff_steps[min(attempt - 1, len(backoff_steps) - 1)] + random.uniform(0.0, 0.35)
                    time.sleep(wait_s)
                else:
                    logger.warning(f"⚠️ Socket attempt {attempt}/{max_retries} encountered: {e}")
            except Exception as e:
                last_error = f"Error: {e}"
                if self.proxy is not None and self._is_proxy_dead_error(e):
                    proxy_dead = True
                logger.warning(f"⚠️ Attempt {attempt}/{max_retries} error: {e}")
                if attempt < max_retries:
                    wait_s = backoff_steps[min(attempt - 1, len(backoff_steps) - 1)] + random.uniform(0.0, 0.35)
                    time.sleep(wait_s)
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        return False, last_error

    def _claim_mailbox_stream(
        self,
        sock: socket.socket,
        session_key: str,
        start_seq: int = 2,
        max_mail_tries: int = 1
    ) -> Tuple[list, int]:
        """
        Execute mailbox operations over an established TCP connection:
        1. QueryMailBox -> parse mail list (1 query per session_key; caller re-logins if DB needs refresh)
        2. ObtainAttachment ("") -> claim all rewards (Nhận nhanh)
        3. DeleteMail ("") -> clean read mails (Xóa đã đọc)
        Returns (claimed_items, next_seq).
        """
        claimed_items = []
        seq = start_seq
        try:
            mails = []
            for mail_try in range(max_mail_tries):
                mail_req = json.dumps([{"func": "QueryMailBox"}], separators=(',', ':'))
                m_body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(mail_req)}"
                    f"&seq={seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')
                sock.sendall(self._pack_packet(seq_num=seq, form_body=m_body, opcode=0))

                m_resp = self._recv_all(
                    sock,
                    target_keyword="QueryMailBoxResult",
                    raise_on_error=True,
                    timeout_sec=8.0
                )
                m_text = m_resp.decode('utf-8', errors='ignore')

                if "QueryMailBoxResult" in m_text:
                    try:
                        mail_obj = self._extract_func_object(m_text, "QueryMailBoxResult")
                        if mail_obj is not None:
                            raw_mails = mail_obj.get("mails", [])
                            if isinstance(raw_mails, list):
                                mails = raw_mails
                    except Exception as e:
                        logger.warning(f"Error parsing QueryMailBoxResult: {e}")

                if mails:
                    break
                if mail_try < max_mail_tries - 1:
                    seq += 1
                    logger.info(f"   ⏳ Hòm thư chưa thấy thư mới, đợi 1.5s để máy chủ chuyển quà (Lần {mail_try + 1}/{max_mail_tries})...")
                    time.sleep(1.5)

            if not mails:
                return [], seq + 1

            logger.info(f"📬 Tìm thấy {len(mails)} thư trong hòm thư:")
            for m in mails:
                subject = m.get("subject", "Không có tiêu đề")
                sender = m.get("sender", "Hệ thống")
                att = m.get("attachment", {}).get("items", [])
                items_desc = ", ".join([f"ID {it.get('contentID')}: x{it.get('count')}" for it in att]) if att else "Không có đính kèm"
                logger.info(f"   ✉️ [{sender}] {subject} | Đính kèm: {items_desc}")

            # 2. ObtainAttachment: gửi nhận theo mail_id cụ thể nếu có, hoặc "" (Nhận nhanh tất cả)
            seq += 1
            mail_ids_to_claim = [str(m.get("id")) for m in mails if m.get("id")]
            target_mail_id = mail_ids_to_claim[0] if len(mail_ids_to_claim) == 1 else ""

            claim_req = json.dumps([{"func": "ObtainAttachment", "mailid": target_mail_id}], separators=(',', ':'))
            c_body = (
                f"bv=70%2E0%2E0&request={game_urlencode(claim_req)}"
                f"&seq={seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=seq, form_body=c_body, opcode=0))

            # Timeout linh hoạt 15.0s để chống nghẽn DB server game Zone 2163 lúc cao điểm
            c_resp = self._recv_all(
                sock,
                target_keyword="ObtainAttachmentResult",
                raise_on_error=True,
                timeout_sec=15.0
            )
            c_text = c_resp.decode('utf-8', errors='ignore')

            # Extract UpdateItem results
            import re
            item_matches = re.findall(r'\{"contentID":(\d+),"contentType":\d+,"count":(\d+)\}', c_text)
            if not item_matches:
                item_matches = re.findall(r'\{"count":(\d+),"contentType":\d+,"contentID":(\d+)\}', c_text)
                item_matches = [(cid, cnt) for cnt, cid in item_matches]

            for cid, cnt in item_matches:
                claimed_items.append({"contentID": int(cid), "count": int(cnt)})
                logger.info(f"   🎁 Đã nhận thành công: Vật phẩm ID {cid} x{cnt}")

            if "ObtainAttachmentResult" in c_text:
                logger.info("   ✅ Đã bấm [Nhận nhanh] toàn bộ quà đính kèm thành công!")

            # 3. DeleteMail (Xóa đã đọc - mailid: "") - non-blocking short read so proxy doesn't idle-timeout
            seq += 1
            del_req = json.dumps([{"func": "DeleteMail", "mailid": ""}], separators=(',', ':'))
            d_body = (
                f"bv=70%2E0%2E0&request={game_urlencode(del_req)}"
                f"&seq={seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=seq, form_body=d_body, opcode=0))

            d_resp = self._recv_all(sock, target_keyword="DeleteMailResult", timeout_sec=1.5)
            if "DeleteMailResult" in d_resp.decode('utf-8', errors='ignore'):
                logger.info("   🗑️ Đã xóa thư đã đọc, hòm thư sạch sẽ!")

            return claimed_items, seq + 1

        except (socket.error, OSError) as e:
            if not claimed_items:
                # Chưa nhận được vé mà đứt socket -> ném lỗi ra ngoài để claim_mailbox tự động reconnect thử lại ngay!
                raise
            logger.info(f"   ℹ️ Đã nhận vé xong, kết nối đóng sớm khi dọn thư ({e}). Tiếp tục bước tiếp theo.")
            return claimed_items, seq + 1
        except Exception as e:
            logger.warning(f"⚠️ Lỗi khi nhận thư: {e}")
            return claimed_items, seq + 1

    def _create_and_login_socket(
        self,
        user_id: str,
        game_zone_id: str,
        dev_id: str,
        force_direct: bool = False
    ) -> Tuple[socket.socket, str, str, int]:
        """Helper to create TCP socket, perform handshake, and login to get session_key."""
        host, port = self.resolve_server(game_zone_id)
        zone_int = int(game_zone_id) if str(game_zone_id).isdigit() else 4
        sock = self._create_socket(force_direct=force_direct)
        sock.settimeout(self.timeout)
        try:
            sock.connect((host, port))

            # Handshake (dynamic header-based)
            sock.sendall(self._pack_packet(seq_num=5, opcode=0x0a))
            hs = self._recv_handshake(sock)
            if len(hs) < 16:
                raise socket.error("Server closed connection during initial handshake")

            # Login
            dev_info = {
                "appVersion": "73.0.0",
                "appBaseVersion": "70.0.0",
                "deviceId": dev_id,
                "combinedDeviceId": "_",
                "deviceCheckChannel": "",
                "deviceType": 17,
                "model": self.model,
                "os": "Android",
                "osversion": self.os_version,
                "mac": self.mac
            }
            login_req = json.dumps([{
                "deviceType": 2,
                "func": "Login",
                "info": json.dumps(dev_info, separators=(',', ':')),
                "serverid": zone_int,
                "userid": f"yuenan#{user_id}"
            }], separators=(',', ':'))

            body = (
                f"bv=70%2E0%2E0&request={game_urlencode(login_req)}"
                f"&seq=1&session=&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=0, form_body=body, opcode=0))

            login_resp = self._recv_all(sock, target_keyword="LoginResult", max_tries=15)
            text = login_resp.decode('utf-8', errors='ignore')
            if "LoginResult" not in text:
                raise socket.error(f"Failed to login on socket: {text or 'empty'}")

            login_obj = self._extract_func_object(text, "LoginResult")
            session_key = login_obj.get("session_key") if login_obj else None
            if not session_key:
                m_sk = re.search(r'"session_key"\s*:\s*"([A-Za-z0-9_]+)"', text)
                session_key = m_sk.group(1) if m_sk else None
            if not session_key:
                raise socket.error(f"Missing session_key in LoginResult: {text[:100]}")

            # ACK
            sock.sendall(self._pack_packet(seq_num=1, opcode=0x14))
            return sock, session_key, host, port
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise

    def auto_lottery_draw_stream(
        self,
        sock: socket.socket,
        session_key: str,
        start_seq: int = 5,
        do_free: bool = True,
        x10_times: int = 1,
        x1_times: int = 10,
        user_id: Optional[str] = None,
        game_zone_id: Optional[str] = None,
        dev_id: Optional[str] = None,
        initial_tickets: Optional[int] = None,
        probe_x10_first: bool = False
    ) -> dict:
        """
        Execute verified 21-draw lottery (Ấp Cao Cấp) with Server Confirmation & Ticket Sweep:
        - Every single draw requires explicit 'LotteryConsumeResult' confirmation from server.
        - Reads real-time remaining ticket balance (ID 80262) from server's 'UpdateItem' packet.
        - If socket drops (EOF / 10053 / 10054 / timeout) before or during response, automatically
          reconnects and re-sends the unconfirmed draw until 0 tickets remain!
        """
        total_ticket_budget = initial_tickets if (initial_tickets is not None and initial_tickets > 0) else (x10_times * 10 + x1_times)
        results = {
            "total_draws": 0,
            "pets": [],
            "items": [],
            "tickets_left": total_ticket_budget,
            "incomplete": False
        }
        active_sock = sock
        active_session = session_key
        seq = start_seq
        import re
        from nature_table import get_nature_info

        def _try_reconnect() -> bool:
            nonlocal active_sock, active_session, seq
            if not user_id or not game_zone_id:
                return False
            logger.info("   🔄 Đang tự động kết nối lại Socket để tiếp tục rút các lượt còn dang dở...")
            try:
                active_sock.close()
            except Exception:
                pass

            last_recon_err = None
            proxy_failed = False
            # Dải thời gian nghỉ thích ứng proxy xoay IP (mất 3-5s để có IP mới)
            for r_idx, wait_s in enumerate((3.5, 4.5, 5.5), 1):
                time.sleep(wait_s + random.uniform(0.0, 0.4))
                try:
                    new_sock, new_sess, _, _ = self._create_and_login_socket(
                        user_id=user_id,
                        game_zone_id=game_zone_id,
                        dev_id=dev_id or f"DEVICE#{user_id}",
                        force_direct=proxy_failed
                    )
                    active_sock = new_sock
                    active_session = new_sess
                    seq = 2
                    logger.info("   ✅ Đã kết nối lại Socket thành công! Tiếp tục rút các vé còn lại...")
                    return True
                except Exception as e_recon:
                    last_recon_err = e_recon
                    if self.proxy is not None and self._is_proxy_dead_error(e_recon):
                        proxy_failed = True
                        logger.info(f"   🔄 Cổng Proxy không phản hồi ({e_recon}), chuyển sang kết nối trực tiếp ở lần thử tiếp...")
                    elif r_idx < 3:
                        logger.info(f"   🔄 Kết nối lại lần {r_idx}/3 chưa thành công ({e_recon}), đang thử lại...")

            logger.warning(f"   ❌ Không thể kết nối lại socket ({last_recon_err}). Dừng an toàn và lưu số pet đã rút.")
            return False

        def _extract_ticket_80262_balance(resp_text: str) -> Optional[int]:
            m1 = re.findall(r'\{"contentID":80262,"contentType":\d+,"count":(\d+)\}', resp_text)
            if m1:
                return int(m1[-1])
            m2 = re.findall(r'\{"count":(\d+),"contentType":\d+,"contentID":80262\}', resp_text)
            if m2:
                return int(m2[-1])
            if "DeleteItem" in resp_text and "80262" in resp_text:
                return 0
            return None

        def _parse_draw_response(resp_text: str):
            if "ServerAddPetResult" not in resp_text and "LotteryConsumeResult" not in resp_text:
                return
            # Parse ServerAddPetResult: extracts both Pet name and XingGeID (Tính cách)
            matches = list(re.finditer(r'"name"\s*:\s*"([A-Za-z0-9_]+)"[^}]*?"XingGeID"\s*:\s*(\d+)', resp_text))
            if not matches:
                matches_rev = list(re.finditer(r'"XingGeID"\s*:\s*(\d+)[^}]*?"name"\s*:\s*"([A-Za-z0-9_]+)"', resp_text))
                parsed_pets = [(m.group(2), int(m.group(1))) for m in matches_rev]
            else:
                parsed_pets = [(m.group(1), int(m.group(2))) for m in matches]

            # Fallback simple name match
            if not parsed_pets:
                for p in re.findall(r'"name":"([A-Za-z0-9_]+)"', resp_text):
                    if p not in ["LoginResult", "LotteryConsumeResult", "StatisticsUpdate", "ServerAddPetResult"]:
                        parsed_pets.append((p, 0))

            for p, xid in parsed_pets:
                if p not in ["LoginResult", "LotteryConsumeResult", "StatisticsUpdate", "ServerAddPetResult"]:
                    pet_entry = f"{p}#{xid}" if xid else p
                    results["pets"].append(pet_entry)
                    nat_info = get_nature_info(xid)
                    buff_str = f" ({nat_info['name']}: {nat_info['buff']} {nat_info['nerf']})".strip() if nat_info.get("name") != "Chưa rõ" else ""
                    logger.info(f"   🐾 Nhận được Pet: [ {p} ]{buff_str}!")

            # Parse LotteryConsumeResult itemList
            item_matches = re.findall(r'\{"id":(\d+),"option":\d+,"type":\d+,"value":(\d+)\}', resp_text)
            for iid, val in item_matches:
                results["items"].append({"id": int(iid), "value": int(val)})

        def _execute_verified_draw(lottery_type: int, label: str, max_attempts: int = 4) -> Tuple[bool, Optional[int], Optional[int]]:
            """
            Send LotteryConsume and strictly verify server returned LotteryConsumeResult.
            Returns (confirmed_ok, server_error_code, remaining_ticket_80262).
            """
            nonlocal seq
            for attempt_idx in range(max_attempts):
                try:
                    req = json.dumps([{"func": "LotteryConsume", "lotteryType": lottery_type}], separators=(',', ':'))
                    body = (
                        f"bv=70%2E0%2E0&request={game_urlencode(req)}"
                        f"&seq={seq}&session={active_session}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                    ).encode('utf-8')
                    active_sock.sendall(self._pack_packet(seq_num=seq, form_body=body, opcode=0))
                    resp = self._recv_all(
                        active_sock,
                        target_keyword="LotteryConsumeResult",
                        raise_on_error=True,
                        timeout_sec=10.0
                    )
                    resp_text = resp.decode('utf-8', errors='ignore')
                    if "LotteryConsumeResult" not in resp_text:
                        raise socket.error("Phản hồi thiếu LotteryConsumeResult")

                    seq += 1
                    srv_ticket_bal = _extract_ticket_80262_balance(resp_text)

                    # Check if server returned an explicit error_code != 0 (e.g. out of tickets)
                    err_code = 0
                    err_match = re.search(r'"LotteryConsumeResult"[^}]*?"error_code"\s*:\s*(-?\d+)', resp_text)
                    if not err_match:
                        err_match = re.search(r'"error_code"\s*:\s*(-?\d+)[^}]*?"LotteryConsumeResult"', resp_text)
                    if err_match:
                        err_code = int(err_match.group(1))

                    has_rewards = ("itemList" in resp_text) or ("ServerAddPetResult" in resp_text)
                    if err_code != 0 and not has_rewards:
                        return False, err_code, srv_ticket_bal

                    _parse_draw_response(resp_text)
                    return True, 0, srv_ticket_bal

                except Exception as draw_err:
                    if attempt_idx < max_attempts - 1 and _try_reconnect():
                        logger.info(f"   🔄 {label} chưa nhận xác nhận từ server ({draw_err}), đang gửi rút lại lượt này...")
                        continue
                    logger.warning(f"   ⚠️ {label} thất bại sau {attempt_idx + 1} lần thử: {draw_err}")
                    return False, None, None

            return False, None, None

        tickets_left = total_ticket_budget
        x10_done = 0
        try:
            # 0. Nếu chế độ probe_x10_first: thử rút X10 trước để xác định có vé tồn trong túi không (không đụng vào lượt Free)
            if probe_x10_first:
                ok_p, err_p, srv_p = _execute_verified_draw(1004, "Kiểm tra & Rút X10 vé tồn")
                if ok_p:
                    results["total_draws"] += 10
                    x10_done = 1
                    tickets_left = srv_p if (srv_p is not None) else max(0, tickets_left - 10)
                    logger.info(f"   ✅ Phát hiện vé tồn trong túi & Rút X10 thành công! (Vé còn lại: {tickets_left})")
                    time.sleep(random.uniform(1.2, 2.2))
                elif err_p is not None and err_p != 0:
                    results["tickets_left"] = 0
                    return results, active_sock, seq, active_session
                else:
                    results["incomplete"] = True
                    results["tickets_left"] = tickets_left
                    return results, active_sock, seq, active_session

            # 1. Nhận Free (1 lượt)
            if do_free:
                logger.info("🥚 [Ấp Cao Cấp] Đang rút lượt Miễn Phí hàng ngày (Free Draw)...")
                ok_f, err_f, srv_bal = _execute_verified_draw(1003, "Lượt Free Draw")
                if ok_f:
                    results["total_draws"] += 1
                    if srv_bal is not None:
                        tickets_left = srv_bal
                elif err_f is None:
                    results["incomplete"] = True
                    results["tickets_left"] = tickets_left
                    return results, active_sock, seq, active_session
                time.sleep(random.uniform(1.2, 2.2))

            # 2. Rút X10 (mỗi lần tiêu 10 vé) khi còn đủ >= 10 vé
            while x10_done < x10_times and tickets_left >= 10:
                logger.info(f"🥚 [Ấp Cao Cấp] Đang thực hiện Rút X10 (Lần {x10_done + 1}/{x10_times}) - Tiêu 10 vé...")
                ok_10, err_10, srv_bal = _execute_verified_draw(1004, f"Lượt Rút X10 (Lần {x10_done + 1})")
                if ok_10:
                    results["total_draws"] += 10
                    x10_done += 1
                    tickets_left = srv_bal if (srv_bal is not None) else max(0, tickets_left - 10)
                    logger.info(f"   ✅ Server xác nhận Rút X10 thành công! (Vé còn lại: {tickets_left})")
                    time.sleep(random.uniform(1.8, 3.0))
                elif err_10 is not None and err_10 != 0:
                    # Server báo không đủ 10 vé -> chuyển sang rút lẻ X1 vét sạch số vé còn lại
                    logger.info(f"   ℹ️ Chuyển sang rút lẻ X1 để vét nốt số vé còn lại (code {err_10})...")
                    break
                else:
                    results["incomplete"] = True
                    results["tickets_left"] = tickets_left
                    return results, active_sock, seq, active_session

            # 3. Rút lẻ X1 vét sạch toàn bộ số vé còn lại đến khi = 0 vé!
            x1_step = 0
            max_x1_safety = 25
            while tickets_left > 0 and x1_step < max_x1_safety:
                x1_step += 1
                logger.info(f"🥚 [Ấp Cao Cấp] Đang thực hiện Rút X1 (Lượt {x1_step} - Còn {tickets_left} vé)...")
                ok_1, err_1, srv_bal = _execute_verified_draw(1003, f"Lượt Rút X1 (Lượt {x1_step})")
                if ok_1:
                    results["total_draws"] += 1
                    tickets_left = srv_bal if (srv_bal is not None) else max(0, tickets_left - 1)
                    time.sleep(random.uniform(0.9, 1.8))
                elif err_1 is not None and err_1 != 0:
                    # Server xác nhận túi đồ đã hết vé 80262
                    logger.info(f"   ℹ️ Máy chủ xác nhận đã rút hết sạch vé trong túi.")
                    tickets_left = 0
                    break
                else:
                    results["incomplete"] = True
                    results["tickets_left"] = tickets_left
                    return results, active_sock, seq, active_session

            results["tickets_left"] = tickets_left
            logger.info(f"✨ [Ấp Cao Cấp] Hoàn thành xác thực {results['total_draws']} lượt rút! (Số vé còn dư: {tickets_left})")
            if results["pets"]:
                logger.info(f"🎉 Danh sách Pet nhận được ({len(results['pets'])}): {', '.join(results['pets'])}")

        except Exception as e:
            logger.warning(f"⚠️ Lỗi khi rút Ấp Cao Cấp: {e}")
            results["incomplete"] = tickets_left > 0
            results["tickets_left"] = tickets_left

        return results, active_sock, seq, active_session
    def claim_mailbox(
        self,
        user_id: str,
        token: str,
        game_zone_id: str = "4",
        device_id: Optional[str] = None,
        auto_draw: bool = True,
        allow_bag_sweep: bool = False,
        has_partial_draws: bool = False
    ) -> Tuple[bool, str, list, dict]:
        """
        Standalone method to connect to Game Server socket, claim all mailbox rewards,
        and optionally execute automatic 21-draw lottery.
        """
        self.activate_web_session(user_id=user_id, token=token)
        self._fetch_server_list(user_id=user_id)
        self._check_account_level(user_id=user_id)

        host, port = self.resolve_server(game_zone_id)
        zone_int = int(game_zone_id) if str(game_zone_id).isdigit() else 4
        if not device_id or device_id.strip() in ("DEVICE#", "DEVICE", ""):
            dev_hash = hashlib.md5(f"DEV_{user_id}".encode()).hexdigest()[:32]
            dev_id = f"DEVICE#{dev_hash}"
        else:
            dev_id = device_id

        max_retries = 6
        last_error = "Unknown socket error"
        proxy_dead = False
        # Dải thời gian nghỉ thích ứng proxy xoay IP (mất 3-5s để có IP mới)
        backoff_steps = (3.5, 4.2, 5.0, 5.5, 6.0)

        for attempt in range(1, max_retries + 1):
            use_direct = (proxy_dead and self.proxy is not None)
            if use_direct:
                logger.warning("   ⚠️ Cổng Proxy không phản hồi, chuyển sang kết nối socket trực tiếp...")
            sock = self._create_socket(force_direct=use_direct)
            sock.settimeout(self.timeout)
            active_sock = sock

            try:
                if attempt > 1:
                    logger.info(f"🔄 Đang kết nối lại Claim Mailbox Socket (Lần {attempt}/{max_retries}) tại {host}:{port}...")
                sock.connect((host, port))
                # Handshake
                sock.sendall(self._pack_packet(seq_num=5, opcode=0x0a))
                hs = self._recv_handshake(sock)
                if len(hs) < 16:
                    raise socket.error("Server closed connection during initial handshake")

                # Login
                dev_info = {
                    "appVersion": "73.0.0",
                    "appBaseVersion": "70.0.0",
                    "deviceId": dev_id,
                    "combinedDeviceId": "_",
                    "deviceCheckChannel": "",
                    "deviceType": 17,
                    "model": self.model,
                    "os": "Android",
                    "osversion": self.os_version,
                    "mac": self.mac
                }
                login_req = json.dumps([{
                    "deviceType": 2,
                    "func": "Login",
                    "info": json.dumps(dev_info, separators=(',', ':')),
                    "serverid": zone_int,
                    "userid": f"yuenan#{user_id}"
                }], separators=(',', ':'))

                body = (
                    f"bv=70%2E0%2E0&request={game_urlencode(login_req)}"
                    f"&seq=1&session=&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
                ).encode('utf-8')
                sock.sendall(self._pack_packet(seq_num=0, form_body=body, opcode=0))

                login_resp = self._recv_all(sock, target_keyword="LoginResult", max_tries=15)
                text = login_resp.decode('utf-8', errors='ignore')
                if "LoginResult" not in text:
                    raise socket.error("Failed to login on socket")

                login_obj = self._extract_func_object(text, "LoginResult")
                session_key = login_obj.get("session_key") if login_obj else None
                if not session_key:
                    m_sk = re.search(r'"session_key"\s*:\s*"([A-Za-z0-9_]+)"', text)
                    session_key = m_sk.group(1) if m_sk else None
                if not session_key:
                    raise socket.error(f"Missing session_key in LoginResult: {text[:100]}")

                # ACK
                sock.sendall(self._pack_packet(seq_num=1, opcode=0x14))

                # 1. Claim mailbox (if initial Step 6 login landed before GM DB commit, Re-Login a fresh session_key)
                # Nếu ObtainAttachment bị timeout mạng, thử kiểm tra vé tồn trong túi đồ trước khi ném lỗi
                try:
                    mail_res = self._claim_mailbox_stream(sock, session_key, start_seq=2)
                    if isinstance(mail_res, tuple):
                        items, next_seq = mail_res
                    else:
                        items, next_seq = mail_res, 5
                except (socket.error, OSError) as mail_err:
                    err_str = str(mail_err)
                    # Nếu chính lệnh ObtainAttachment bị timeout/rớt gói:
                    # Nhiều khả năng server game đã xử lý cộng vé vào túi đồ thành công trước khi rớt phản hồi
                    if "ObtainAttachmentResult" in err_str:
                        logger.info(f"   ℹ️ Gói phản hồi nhận thư bị trễ ({err_str}), tiến hành kiểm tra trực tiếp vé tồn trong túi đồ...")
                        items = []
                        next_seq = 6
                        allow_bag_sweep = True
                    else:
                        raise

                if not items and not allow_bag_sweep:
                    relogin_waits = (1.8, 2.5, 3.5)
                    for relogin_idx, wait_s in enumerate(relogin_waits, 1):
                        logger.info(
                            f"   ⏳ Hòm thư phiên hiện tại chưa cập nhật quà GM, đợi {wait_s:.1f}s rồi Re-Login phiên mới (Lần {relogin_idx}/{len(relogin_waits)})..."
                        )
                        try:
                            sock.close()
                        except Exception:
                            pass
                        time.sleep(wait_s + random.uniform(0.0, 0.3))
                        sock, session_key, _, _ = self._create_and_login_socket(
                            user_id=user_id,
                            game_zone_id=game_zone_id,
                            dev_id=dev_id,
                            force_direct=use_direct
                        )
                        active_sock = sock
                        mail_res = self._claim_mailbox_stream(sock, session_key, start_seq=2)
                        if isinstance(mail_res, tuple):
                            items, next_seq = mail_res
                        else:
                            items, next_seq = mail_res, 5
                        if items:
                            break

                # Kiểm tra chặt chẽ số vé Ấp Cao Cấp (ID 80262) vừa nhận từ hòm thư
                claimed_tickets = sum(
                    int(it.get("count", 0)) for it in items
                    if int(it.get("contentID", 0)) == 80262
                )

                draw_results = {}
                active_sock = sock
                active_session = session_key
                current_seq = next_seq

                if not items:
                    if not (allow_bag_sweep and auto_draw):
                        logger.warning("   ⚠️ Hòm thư chưa có thư/vé quà tặng từ máy chủ. Dừng rút trứng an toàn để không bị lỗi thiếu vé!")
                        return False, "Chưa nhận được vé quà tặng từ hòm thư", [], {}

                    # Chế độ chạy tiếp (pending_draw): kiểm tra & vét vé còn tồn trong túi nếu hòm thư đã nhận trước đó
                    if has_partial_draws:
                        logger.info("   🎟️ Hòm thư đã nhận trước đó, tiến hành vét toàn bộ vé Ấp Cao Cấp còn tồn trong túi...")
                        draw_res = self.auto_lottery_draw_stream(
                            sock,
                            session_key,
                            start_seq=next_seq,
                            do_free=False,
                            x10_times=1,
                            x1_times=20,
                            user_id=user_id,
                            game_zone_id=game_zone_id,
                            dev_id=dev_id,
                            initial_tickets=20,
                            probe_x10_first=False
                        )
                    else:
                        logger.info("   🔎 Hòm thư trống, kiểm tra xem vé đã nằm sẵn trong túi đồ chưa...")
                        draw_res = self.auto_lottery_draw_stream(
                            sock,
                            session_key,
                            start_seq=next_seq,
                            do_free=True,
                            x10_times=1,
                            x1_times=20,
                            user_id=user_id,
                            game_zone_id=game_zone_id,
                            dev_id=dev_id,
                            initial_tickets=20,
                            probe_x10_first=True
                        )

                    if isinstance(draw_res, tuple) and len(draw_res) == 4:
                        draw_results, active_sock, current_seq, active_session = draw_res
                    elif isinstance(draw_res, tuple) and len(draw_res) == 3:
                        draw_results, active_sock, current_seq = draw_res
                    elif isinstance(draw_res, tuple):
                        draw_results, active_sock = draw_res
                    else:
                        draw_results = draw_res

                    if not has_partial_draws and not draw_results.get("incomplete") and draw_results.get("total_draws", 0) == 0:
                        logger.warning("   ⚠️ Hòm thư chưa có thư/vé quà tặng từ máy chủ. Dừng rút trứng an toàn để không bị lỗi thiếu vé!")
                        return False, "Chưa nhận được vé quà tặng từ hòm thư", [], {}
                else:
                    ticket_budget = claimed_tickets if claimed_tickets > 0 else 20
                    logger.info(f"   🎟️ Đã nhận được {len(items)} vật phẩm từ hòm thư (sẵn sàng {ticket_budget} vé). Bắt đầu tiến hành ấp {ticket_budget + 1} lượt...")

                    # 2. Auto lottery draw (verified draws until 0 tickets remain) with Auto-Reconnect
                    # Cấu hình chuẩn vàng gốc: 1 lượt Free + 1 lần Rút X10 (10 vé) + 10 lượt Rút X1 lẻ (10 vé)
                    # Thuật toán game roll Thần Thú / Rate-up (Mesprit) ở các lượt Rút X1 lẻ!
                    if auto_draw:
                        draw_res = self.auto_lottery_draw_stream(
                            sock,
                            session_key,
                            start_seq=next_seq,
                            do_free=True,
                            x10_times=1,
                            x1_times=10,
                            user_id=user_id,
                            game_zone_id=game_zone_id,
                            dev_id=dev_id,
                            initial_tickets=ticket_budget
                        )
                        if isinstance(draw_res, tuple) and len(draw_res) == 4:
                            draw_results, active_sock, current_seq, active_session = draw_res
                        elif isinstance(draw_res, tuple) and len(draw_res) == 3:
                            draw_results, active_sock, current_seq = draw_res
                        elif isinstance(draw_res, tuple):
                            draw_results, active_sock = draw_res
                        else:
                            draw_results = draw_res

                # 3. Synchronize actual Pet inventory from Server via QueryPetList with exact continuous sequence number
                try:
                    server_pets = None
                    if active_sock and not getattr(active_sock, '_closed', False):
                        server_pets = self.query_pet_list_stream(active_sock, active_session, start_seq=current_seq)
                    if server_pets:
                        server_pet_entries = [p["entry"] for p in server_pets if p.get("entry")]
                        if server_pet_entries:
                            draw_results["pets"] = server_pet_entries
                            logger.info(f"✨ [Đồng bộ Kho Pet] Danh sách thực tế trong Kho ({len(server_pet_entries)} Pet): {', '.join(server_pet_entries)}")
                except Exception as ex_sync:
                    logger.debug(f"QueryPetList sync error: {ex_sync}")

                # 4. Tự động kiểm tra và rút Quẻ May Mắn 1 lượt Free (LuckySigh / LuckyDraw)
                try:
                    if active_sock and not getattr(active_sock, '_closed', False):
                        current_seq += 1
                        l_succ, current_seq, l_rew, l_text = self.draw_lucky_free_stream(active_sock, active_session, start_seq=current_seq)
                        if l_succ and l_text:
                            draw_results["lucky_sigh"] = l_text
                            if l_text != "Đã rút":
                                logger.info(f"🎋 [Quẻ May Mắn] Rút 1 lượt Free thành công: {l_text}")
                except Exception as ex_lucky:
                    logger.debug(f"Quẻ May Mắn free draw error: {ex_lucky}")

                if auto_draw and draw_results.get("incomplete") and draw_results.get("tickets_left", 0) > 0:
                    rem = draw_results["tickets_left"]
                    logger.warning(f"   ⚠️ Phiên rút bị ngắt kết nối giữa chừng, vẫn còn {rem} vé trong túi chưa rút hết!")
                    return False, f"Còn {rem} vé trong túi chưa rút hết do mất kết nối mạng", items, draw_results

                return True, "Mailbox and 21-lottery completed successfully", items, draw_results

            except (socket.error, ConnectionResetError, socket.timeout) as e:
                last_error = f"Socket error: {e}"
                if self.proxy is not None and self._is_proxy_dead_error(e):
                    proxy_dead = True
                if attempt < max_retries:
                    logger.info(f"🔄 Socket nhận thư nghẽn ({e}), đang tự động kết nối lại lần {attempt + 1}/{max_retries}...")
                    wait_s = backoff_steps[min(attempt - 1, len(backoff_steps) - 1)] + random.uniform(0.0, 0.4)
                    time.sleep(wait_s)
                else:
                    logger.warning(f"⚠️ Claim mailbox socket thất bại sau {max_retries} lần thử: {e}")
            except Exception as e:
                last_error = f"Error: {e}"
                if self.proxy is not None and self._is_proxy_dead_error(e):
                    proxy_dead = True
                if attempt < max_retries:
                    logger.info(f"🔄 Thử lại kết nối nhận thư lần {attempt + 1}/{max_retries} ({e})...")
                    wait_s = backoff_steps[min(attempt - 1, len(backoff_steps) - 1)] + random.uniform(0.0, 0.4)
                    time.sleep(wait_s)
                else:
                    logger.warning(f"⚠️ Claim mailbox thất bại sau {max_retries} lần thử: {e}")
            finally:
                try:
                    sock.close()
                except Exception:
                    pass
                if active_sock and active_sock is not sock:
                    try:
                        active_sock.close()
                    except Exception:
                        pass

        return False, last_error, [], {}

    def query_pet_list_stream(self, sock: socket.socket, session_key: str, start_seq: int = 2) -> list:
        """
        Query complete pet list (Toan bo Pet so huu) via TCP Socket.
        Sends QueryPetList, receives dual-header zlib compressed packet,
        and parses all Pet entries with their exact XingGeID (Tinh cach).
        Returns list of pet dicts.
        """
        import zlib
        from nature_table import get_nature_info

        try:
            req_json = json.dumps([{"func": "QueryPetList"}], separators=(',', ':'))
            body = (
                f"bv=70%2E0%2E0&request={game_urlencode(req_json)}"
                f"&seq={start_seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=start_seq, form_body=body, opcode=0))

            resp = self._recv_all(sock, target_keyword="PetList", timeout_sec=6.0)
            if not resp:
                return []

            text = resp.decode('utf-8', errors='ignore')
            raw_pets = None
            pet_obj = self._extract_func_object(text, "QueryPetListResult")
            if pet_obj is not None and isinstance(pet_obj.get("PetList"), list):
                raw_pets = pet_obj["PetList"]
            else:
                for line in text.splitlines():
                    line_s = line.strip()
                    if "PetList" not in line_s:
                        continue
                    s_idx = line_s.find("[")
                    e_idx = line_s.rfind("]")
                    if s_idx != -1 and e_idx > s_idx:
                        try:
                            parsed = json.loads(line_s[s_idx:e_idx + 1])
                            if isinstance(parsed, list):
                                for item in parsed:
                                    if isinstance(item, dict) and isinstance(item.get("PetList"), list):
                                        raw_pets = item["PetList"]
                                        break
                            if raw_pets is not None:
                                break
                        except Exception:
                            continue

            if not raw_pets:
                return []
            parsed_pets = []
            for p in raw_pets:
                name = p.get('name', '')
                xid = int(p.get('XingGeID', 0))
                nat = get_nature_info(xid)
                parsed_pets.append({
                    "name": name,
                    "xingge_id": xid,
                    "nature": nat,
                    "level": p.get('level', 1),
                    "fighting": p.get('Fighting', 0),
                    "entry": f"{name}#{xid}" if xid else name
                })
            return parsed_pets
        except Exception as e:
            logger.debug(f"Error querying pet list: {e}")
            return []

    def draw_lucky_free_stream(
        self,
        sock: socket.socket,
        session_key: str,
        start_seq: int = 15
    ) -> Tuple[bool, int, list, str]:
        """
        Kiểm tra và rút 1 lượt Quẻ May Mắn miễn phí (Operation Activity ID 94 - 'Quẻ may mắn') qua TCP Socket.
        1. Gửi QueryOA để kiểm tra sự kiện ID 94 ("Quẻ may mắn").
        2. Nếu index 0 có drawCount == 1 -> đã rút.
        3. Nếu index 0 có drawCount == 0 -> gửi OADraw oaType=94, index=0.
        4. Bóc tách OADrawLoot / UpdateItem để lấy danh sách quà.
        Trả về: (thành_công: bool, seq_tiếp_theo: int, danh_sách_quà: list, tóm_tắt_quà: str)
        """
        seq = start_seq
        item_map = {
            # 13 Vật phẩm chuẩn sự kiện Quẻ May Mắn (HT_OA_LUCKYSIGH_LOOT_List)
            29205: "Sao Đất Khô",         # Đại Cát (x1)
            80116: "Mảnh Thường",         # Cát (x1000)
            6513:  "Hóa Thạch Lileep",     # Cát (x1)
            17013: "Bí Truyền-Sử",        # Cát (x10)
            80198: "Dấu Z",               # Cát (x750)
            6202:  "Bóng mừng lễ",        # Tiểu Cát (x1)
            17036: "Hộp Makeup-Cao",      # Tiểu Cát (x20)
            70025: "Thẻ Đột Phá",         # Tiểu Cát (x80)
            17053: "Bí Truyền-Master",    # Tiểu Cát (x10)
            7506:  "Hoeruko Doll",        # Hòa (x1)
            14001: "Quả Pokemon",         # Hòa (x500)
            70027: "Thẻ EXP Gộp",         # Hòa (x100)
            70005: "Đá Tẩy Tư Chất",      # Hòa (x12)
            # Các vật phẩm tiền tệ / tài nguyên khác
            4001: "Vàng",
            4002: "EXP",
            4020: "Kim Cương",
            80001: "Bánh Mì Thể Lực",
            80261: "Vé Ấp Thường",
            80262: "Vé Ấp Cao Cấp",
            90001: "Mảnh Vạn Năng",
        }
        try:
            # 1. Truy vấn QueryOA để tìm sự kiện ID 94 (Quẻ may mắn)
            req_query = json.dumps([{"func": "QueryOA"}], separators=(',', ':'))
            body_q = (
                f"bv=70%2E0%2E0&request={game_urlencode(req_query)}"
                f"&seq={seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=seq, form_body=body_q, opcode=0))

            resp_q = self._recv_all(sock, target_keyword="QueryOAResult", timeout_sec=4.0)
            seq += 1

            oa_94 = None
            if resp_q:
                q_text = resp_q.decode('utf-8', errors='ignore')
                q_obj = self._extract_func_object(q_text, "QueryOAResult")
                if q_obj and q_obj.get("activities"):
                    for act in q_obj["activities"]:
                        if act.get("id") == 94 or "quẻ" in str(act.get("name", "")).lower():
                            oa_94 = act
                            break

            if not oa_94:
                return False, seq, [], ""

            # Kiểm tra thời gian kết thúc sự kiện
            now_ts = int(time.time())
            if oa_94.get("endTime") and now_ts > oa_94["endTime"]:
                return True, seq, [], "Đã hết hạn"

            rewards = oa_94.get("rewards", [])
            # Slot 0 là lượt rút free đầu tiên của sự kiện Quẻ may mắn
            draw_cnt = rewards[0].get("drawCount", 0) if rewards else 0
            if draw_cnt > 0:
                return True, seq, [], "Đã rút"

            # 2. Gửi OADraw với index=0 để rút lượt free
            req_draw = json.dumps([{
                "func": "OADraw",
                "oaType": 94,
                "index": 0,
                "paraList": []
            }], separators=(',', ':'))
            body_d = (
                f"bv=70%2E0%2E0&request={game_urlencode(req_draw)}"
                f"&seq={seq}&session={session_key}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=seq, form_body=body_d, opcode=0))
            resp_d = self._recv_all(sock, target_keyword="OADrawResult", timeout_sec=4.0)
            seq += 1

            if not resp_d:
                return False, seq, [], "Mạng timeout khi rút"

            d_text = resp_d.decode('utf-8', errors='ignore')
            loot_items = []

            # Bóc tách từ OADrawLoot
            loot_obj = self._extract_func_object(d_text, "OADrawLoot")
            if loot_obj and loot_obj.get("lootList"):
                for it in loot_obj["lootList"]:
                    loot_items.append((it.get("id") or 0, it.get("value") or 1))

            # Bóc tách bổ sung từ UpdateItem nếu có
            if not loot_items and "UpdateItem" in d_text:
                import re
                m_items = re.findall(r'"contentID"\s*:\s*(\d+)[^}]*?"count"\s*:\s*(\d+)', d_text)
                for i_id, cnt in m_items:
                    loot_items.append((int(i_id), int(cnt)))

            d_obj = self._extract_func_object(d_text, "OADrawResult")
            if d_obj and d_obj.get("error_code") == 2:
                return True, seq, [], "Đã rút"

            if loot_items:
                reward_strs = []
                for i_id, cnt in loot_items:
                    name = item_map.get(i_id)
                    if not name:
                        if 20000 <= i_id <= 39999:
                            name = f"Mảnh Pet {i_id}"
                        else:
                            name = f"Vật phẩm {i_id}"
                    reward_strs.append(f"{name} x{cnt}" if cnt > 1 else str(name))
                summary = ", ".join(reward_strs) if reward_strs else "Thành công (1 lượt)"
                return True, seq, loot_items, summary

            if d_obj and d_obj.get("error_code") == 0:
                return True, seq, [], "Thành công (1 lượt)"

            return False, seq, [], ""

        except Exception as e:
            logger.debug(f"draw_lucky_free_stream error: {e}")
            return False, seq + 1, [], ""

    def query_account_pets(
        self,
        user_id: str,
        token: str,
        game_zone_id: str = "4",
        device_id: Optional[str] = None,
        lucky_out: Optional[dict] = None
    ) -> list:
        """
        Standalone method to connect to Game Server socket, login, and query
        all owned pets with their exact XingGeID (Tinh cach).
        """
        self.activate_web_session(user_id=user_id, token=token)
        self._fetch_server_list(user_id=user_id)
        self._check_account_level(user_id=user_id)

        host, port = self.resolve_server(game_zone_id)
        zone_int = int(game_zone_id) if str(game_zone_id).isdigit() else 4
        if not device_id or device_id.strip() in ("DEVICE#", "DEVICE", ""):
            dev_hash = hashlib.md5(f"DEV_{user_id}".encode()).hexdigest()[:32]
            dev_id = f"DEVICE#{dev_hash}"
        else:
            dev_id = device_id

        create_sock_fn = getattr(self, '_create_socket', None)
        if callable(create_sock_fn):
            sock = self._create_socket(force_direct=True)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            sock.connect((host, port))
            sock.sendall(self._pack_packet(seq_num=5, opcode=0x0a))
            hs = self._recv_handshake(sock)

            dev_info = {
                "appVersion": "73.0.0",
                "appBaseVersion": "70.0.0",
                "deviceId": dev_id,
                "combinedDeviceId": "_",
                "deviceCheckChannel": "",
                "deviceType": 17,
                "model": self.model,
                "os": "Android",
                "osversion": self.os_version,
                "mac": self.mac
            }
            login_req = json.dumps([{
                "deviceType": 2,
                "func": "Login",
                "info": json.dumps(dev_info, separators=(',', ':')),
                "serverid": zone_int,
                "userid": f"yuenan#{user_id}"
            }], separators=(',', ':'))

            body = (
                f"bv=70%2E0%2E0&request={game_urlencode(login_req)}"
                f"&seq=1&session=&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            ).encode('utf-8')
            sock.sendall(self._pack_packet(seq_num=0, form_body=body, opcode=0))

            login_resp = self._recv_all(sock, target_keyword="LoginResult", max_tries=15)
            text = login_resp.decode('utf-8', errors='ignore')
            if "LoginResult" not in text:
                return []

            import re
            m = re.search(r'"session_key"\s*:\s*"([A-Za-z0-9_]+)"', text)
            if not m:
                return []
            session_key = m.group(1)

            # ACK
            sock.sendall(self._pack_packet(seq_num=1, opcode=0x14))

            # Query Pet List
            pets = self.query_pet_list_stream(sock, session_key, start_seq=2)
            if lucky_out is not None:
                try:
                    l_succ, _, _, l_text = self.draw_lucky_free_stream(sock, session_key, start_seq=3)
                    if l_succ and l_text:
                        lucky_out["lucky_sigh"] = l_text
                        if l_text != "Đã rút":
                            logger.info(f"🎋 [Quẻ May Mắn] Rút lượt Free thành công: {l_text}")
                except Exception:
                    pass
            return pets
        except Exception as e:
            logger.warning(f"Error querying account pets for {user_id}: {e}")
            return []
        finally:
            try:
                sock.close()
            except Exception:
                pass

