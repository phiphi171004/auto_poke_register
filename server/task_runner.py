"""
Task runner, WebSocket event hub, live server fetcher, and concurrent proxy checker
for Pokemon Auto Register Web.

Handles spawning engine/main.py cross-platform (Windows local & Linux/Render),
streaming stdout/stderr logs in real time over WebSocket, mirroring newly written
accounts into Supabase automatically, and running concurrent TCP proxy checks.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import signal
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import httpx
from fastapi import WebSocket

from .storage import DATA_DIR, WEB_ROOT, StorageManager

logger = logging.getLogger("pokemon_web.task_runner")

ENGINE_DIR = WEB_ROOT / "engine"
MAIN_PY_PATH = ENGINE_DIR / "main.py"

SERVERLIST_URL = "http://vn-login.pokedaichien.pocketgamesol.com/serverlist/serverlist.php"
SERVERLIST_SALT = "D#L!S@O#*!"

_SAVED_USER_RE = re.compile(
    r"(?:Đã lưu tài khoản|Hoàn tất thành công tài khoản|Hoàn tất đồng bộ)\s+['\"]([a-zA-Z0-9_]+)['\"]"
)


class ConnectionManager:
    """Thread-safe / asyncio-safe WebSocket broadcast hub."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def send_personal(self, websocket: WebSocket, event: str, data: Any = None) -> None:
        try:
            await websocket.send_json({"event": event, "data": data})
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, event: str, data: Any = None) -> None:
        if not self._connections:
            return
        payload = {"event": event, "data": data}
        dead: List[WebSocket] = []
        # Snapshot set before awaiting
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


def _classify_log_line(line: str, is_resume: bool = False) -> str:
    """Match exact log classification rules from gui_app/main.js."""
    if (
        "Nhận được Pet:" in line
        or "🐾" in line
        or (is_resume and "Hoàn tất thành công" in line)
    ):
        return "pet"
    if "Thành công" in line or "✅" in line or "🎉" in line or "✨" in line:
        return "success"
    if "Ấp Cao Cấp" in line or "🥚" in line:
        return "gacha"
    if "Hòm thư" in line or "📬" in line or "Thưởng nâng cấp" in line:
        return "mail"
    if "Lỗi" in line or "❌" in line or "⚠️" in line or "warning" in line.lower():
        return "warning"
    return "normal"


def _now_time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _parse_host_port(raw_proxy: str) -> Tuple[str, int]:
    """Parse proxy host & port from any supported format (matches gui_app/main.js)."""
    trimmed = raw_proxy.strip()
    clean = re.sub(r"^[a-zA-Z0-9]+://", "", trimmed)
    host = ""
    port = 0
    if "@" in clean:
        host_port = clean.rsplit("@", 1)[-1]
        hp = host_port.split(":")
        host = (hp[0] if len(hp) > 0 else "").strip()
        port_str = (hp[1] if len(hp) > 1 else "").strip()
        port = int(port_str) if port_str.isdigit() else 0
    else:
        parts = clean.split(":")
        if len(parts) >= 2:
            host = parts[0].strip()
            port_str = parts[1].strip()
            port = int(port_str) if port_str.isdigit() else 0
    return host, port


class TaskRunner:
    """Manages engine subprocesses, real-time logs, server refresh, and proxy checking."""

    def __init__(self, storage: StorageManager, ws_manager: ConnectionManager) -> None:
        self.storage = storage
        self.ws = ws_manager
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task[Any]] = None
        self._sync_task: Optional[asyncio.Task[Any]] = None
        self._lock = asyncio.Lock()
        self.current_mode: Optional[str] = None  # "register" | "resume" | None
        self._dirty_usernames: Set[str] = set()
        self._last_bg_server_refresh: float = 0.0
        self._proxy_file_path: Path = DATA_DIR / "proxies_runtime.txt"

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def _build_engine_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env["POKEMON_DB_PATH"] = str(self.storage.db_path)
        env["POKEMON_LOG_PATH"] = str(DATA_DIR / "auto_register.log")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _write_proxy_file(self, proxies: Union[List[str], str, None]) -> Optional[Path]:
        if proxies is None:
            return None
        lines = proxies.splitlines() if isinstance(proxies, str) else list(proxies)
        valid = [str(p).strip() for p in lines if str(p).strip() and not str(p).strip().startswith("#")]
        if not valid:
            return None
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._proxy_file_path.write_text("\n".join(valid), encoding="utf-8")
        return self._proxy_file_path

    async def _terminate_process(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            if sys.platform == "win32":
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/pid",
                    str(proc.pid),
                    "/f",
                    "/t",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), timeout=5.0)
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    return
                except Exception:
                    proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        proc.kill()
        except Exception as exc:
            logger.warning("Error stopping engine process (pid=%s): %s", proc.pid, exc)
            try:
                proc.kill()
            except Exception:
                pass

    async def shutdown(self) -> None:
        if self._process is not None and self._process.returncode is None:
            await self._terminate_process(self._process)
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()

    # ------------------------------------------------------------------
    # Engine Subprocess Streaming & Auto Supabase Sync
    # ------------------------------------------------------------------
    async def _periodic_supabase_sync(self) -> None:
        """Flush newly written SQLite accounts to Supabase periodically while engine runs."""
        if not self.storage.use_supabase:
            return
        try:
            while self.is_running:
                await asyncio.sleep(4.0)
                if self._dirty_usernames:
                    batch = list(self._dirty_usernames)
                    self._dirty_usernames.clear()
                    try:
                        await self.storage.sync_local_accounts_to_supabase(batch)
                    except Exception as exc:
                        logger.warning("Periodic Supabase sync error: %s", exc)
                        self._dirty_usernames.update(batch)
        except asyncio.CancelledError:
            return

    async def _monitor_process(
        self, proc: asyncio.subprocess.Process, mode: str
    ) -> None:
        is_resume = mode == "resume"

        async def _read_stdout() -> None:
            assert proc.stdout is not None
            while True:
                raw_line = await proc.stdout.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line.strip():
                    continue

                log_type = _classify_log_line(line, is_resume=is_resume)
                await self.ws.broadcast(
                    "log-message",
                    {"text": line, "type": log_type, "time": _now_time_str()},
                )

                if "Đã lưu tài khoản" in line or "Hoàn tất thành công" in line:
                    m = _SAVED_USER_RE.search(line)
                    extracted_user = m.group(1) if m else None
                    if self.storage.use_supabase:
                        if extracted_user:
                            self._dirty_usernames.add(extracted_user)
                            try:
                                await self.storage.sync_local_accounts_to_supabase([extracted_user])
                                self._dirty_usernames.discard(extracted_user)
                            except Exception as exc:
                                logger.warning("Immediate Supabase sync failed for %s: %s", extracted_user, exc)
                        else:
                            try:
                                await self.storage.sync_local_accounts_to_supabase()
                            except Exception as exc:
                                logger.warning("Immediate Supabase full sync failed: %s", exc)
                    await self.ws.broadcast("account-added", {"username": extracted_user})

        async def _read_stderr() -> None:
            assert proc.stderr is not None
            while True:
                raw_line = await proc.stderr.readline()
                if not raw_line:
                    break
                text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not text.strip():
                    continue
                await self.ws.broadcast(
                    "log-message",
                    {"text": text, "type": "warning", "time": _now_time_str()},
                )

        try:
            await asyncio.gather(_read_stdout(), _read_stderr())
            code = await proc.wait()
        except asyncio.CancelledError:
            code = proc.returncode if proc.returncode is not None else -1
        except Exception as exc:
            logger.error("Error monitoring engine process: %s", exc)
            code = proc.returncode if proc.returncode is not None else -1
        finally:
            if self._sync_task and not self._sync_task.done():
                self._sync_task.cancel()
            self._sync_task = None

            # Final flush of any accounts saved during this run into Supabase
            if self.storage.use_supabase:
                try:
                    pending_users = list(self._dirty_usernames) if self._dirty_usernames else None
                    self._dirty_usernames.clear()
                    await self.storage.sync_local_accounts_to_supabase(pending_users)
                except Exception as exc:
                    logger.warning("Final Supabase sync failed: %s", exc)

            if self._process is proc:
                self._process = None
                self.current_mode = None

            finish_label = (
                f"Tiến trình chạy tiếp đã kết thúc (Exit code: {code})"
                if is_resume
                else f"Tiến trình đã kết thúc (Exit code: {code})"
            )
            await self.ws.broadcast(
                "log-message",
                {
                    "text": finish_label,
                    "type": "success" if code == 0 else "warning",
                    "time": _now_time_str(),
                },
            )
            await self.ws.broadcast("task-status", {"running": False, "mode": None})
            await self.ws.broadcast("task-finished", {"code": code})
            await self.ws.broadcast("account-added", {})

    async def _spawn_engine(self, args: List[str], mode: str) -> Dict[str, Any]:
        if not MAIN_PY_PATH.exists():
            return {"success": False, "message": f"Không tìm thấy engine tại {MAIN_PY_PATH}"}

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(ENGINE_DIR),
            "env": self._build_engine_env(),
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "limit": 1024 * 1024,  # 1MB line buffer for verbose JSON/logs
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-u", str(MAIN_PY_PATH), *args, **popen_kwargs
            )
        except Exception as exc:
            logger.error("Failed to spawn engine/main.py: %s", exc)
            return {"success": False, "message": f"Lỗi khởi chạy Python: {exc}"}

        self._process = proc
        self.current_mode = mode
        self._dirty_usernames.clear()

        await self.ws.broadcast("task-status", {"running": True, "mode": mode})
        self._sync_task = asyncio.create_task(self._periodic_supabase_sync())
        self._reader_task = asyncio.create_task(self._monitor_process(proc, mode))

        msg = "Bắt đầu chạy tiếp tài khoản..." if mode == "resume" else "Bắt đầu thành công"
        return {"success": True, "message": msg}

    # ------------------------------------------------------------------
    # Public Task Controls
    # ------------------------------------------------------------------
    async def start_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            if self.is_running:
                return {
                    "success": False,
                    "message": "Đang có tiến trình chạy! Vui lòng dừng lại trước.",
                }

            count = max(1, int(config.get("count", 1) or 1))
            zone = str(config.get("zone", "2160") or "2160").strip()
            delay_min = float(config.get("delayMin", 1.5))
            delay_max = float(config.get("delayMax", 3.0))
            max_per_minute = max(1, int(config.get("maxPerMinute", 100) or 100))
            visitor_upgrade = bool(config.get("visitorUpgrade", True))
            claim_mail = bool(config.get("claimMail", True))
            auto_draw = bool(config.get("autoDraw", True))
            custom_username = (config.get("customUsername") or "").strip()
            custom_password = (config.get("customPassword") or "").strip()
            auto_increment = bool(config.get("autoIncrementUsername", True))
            threads = max(1, min(100, int(config.get("threads", 1) or 1)))
            network_mode = str(config.get("networkMode", "direct") or "direct").strip().lower()
            proxy_type = str(config.get("proxyType", "http") or "http").strip().lower()
            if proxy_type not in ("http", "https", "socks5"):
                proxy_type = "http"
            proxies = config.get("proxies", [])

            args = [
                "--count", str(count),
                "--zone", zone,
                "--delay-min", str(delay_min),
                "--delay-max", str(delay_max),
                "--max-per-minute", str(max_per_minute),
                "--threads", str(threads),
            ]
            if not visitor_upgrade:
                args.append("--normal")
            if not claim_mail:
                args.append("--no-mail")
            if not auto_draw:
                args.append("--no-draw")
            if custom_username:
                args.extend(["--username", custom_username])
                if not auto_increment:
                    args.append("--no-increment")
            if custom_password:
                args.extend(["--password", custom_password])

            if network_mode == "proxy":
                proxy_file = self._write_proxy_file(proxies)
                if proxy_file:
                    args.extend(["--proxy-file", str(proxy_file), "--proxy-type", proxy_type])

            return await self._spawn_engine(args, mode="register")

    async def resume_pending(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._lock:
            if self.is_running:
                return {
                    "success": False,
                    "message": "Đang có tiến trình chạy! Vui lòng dừng lại trước.",
                }

            cfg = params or {}
            username = (cfg.get("username") or "").strip() or None
            threads = max(1, min(100, int(cfg.get("threads", 1) or 1)))
            network_mode = str(cfg.get("networkMode", "direct") or "direct").strip().lower()
            proxy_type = str(cfg.get("proxyType", "socks5") or "socks5").strip().lower()
            if proxy_type not in ("http", "https", "socks5"):
                proxy_type = "socks5"
            proxies = cfg.get("proxies", [])

            # Ensure Supabase pending accounts are hydrated in local SQLite before engine reads them
            if self.storage.use_supabase:
                await self.storage.hydrate_local_sqlite_from_supabase(
                    username=username,
                    pending_only=(username is None),
                )

            args = ["--resume", "--threads", str(threads)]
            if username:
                args.extend(["--resume-user", username])

            if network_mode == "proxy":
                proxy_file = self._write_proxy_file(proxies)
                if proxy_file:
                    args.extend(["--proxy-file", str(proxy_file), "--proxy-type", proxy_type])

            return await self._spawn_engine(args, mode="resume")

    async def stop_task(self) -> Dict[str, Any]:
        async with self._lock:
            if not self.is_running or self._process is None:
                return {"success": False, "message": "Không có tiến trình nào đang chạy"}
            proc = self._process
            await self._terminate_process(proc)
            return {"success": True, "message": "Đã dừng tiến trình!"}

    async def sync_account_pets(self, username: str) -> Dict[str, Any]:
        clean_user = (username or "").strip()
        if not clean_user:
            return {
                "success": False,
                "username": "",
                "message": "Tên tài khoản không hợp lệ!",
                "pets": [],
                "count": 0,
            }

        # Hydrate single account from Supabase into local SQLite so engine can look up token/user_id/zone_id
        if self.storage.use_supabase:
            await self.storage.hydrate_local_sqlite_from_supabase(username=clean_user)

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(ENGINE_DIR),
            "env": self._build_engine_env(),
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "limit": 1024 * 1024,
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-u", str(MAIN_PY_PATH), "--sync-user", clean_user, **popen_kwargs
            )
        except Exception as exc:
            return {
                "success": False,
                "username": clean_user,
                "message": f"Lỗi khởi chạy đồng bộ: {exc}",
                "pets": [],
                "count": 0,
            }

        stdout_lines: List[str] = []

        async def _consume_stdout() -> None:
            assert proc.stdout is not None
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                stdout_lines.append(line)
                if not line.strip() or "SYNC_RESULT_JSON:" in line:
                    continue
                log_type = "normal"
                if "🎉" in line or "✅" in line:
                    log_type = "success"
                elif "❌" in line or "⚠️" in line:
                    log_type = "warning"
                await self.ws.broadcast(
                    "log-message",
                    {"text": line, "type": log_type, "time": _now_time_str()},
                )

        async def _consume_stderr() -> None:
            assert proc.stderr is not None
            await proc.stderr.read()

        try:
            await asyncio.wait_for(asyncio.gather(_consume_stdout(), _consume_stderr()), timeout=60.0)
            code = await proc.wait()
        except asyncio.TimeoutError:
            await self._terminate_process(proc)
            return {
                "success": False,
                "username": clean_user,
                "message": "Hết thời gian chờ đồng bộ kho Pet từ máy chủ game (60s)",
                "pets": [],
                "count": 0,
            }

        # Sync updated pets/lucky_sigh back to Supabase
        if self.storage.use_supabase:
            try:
                await self.storage.sync_local_accounts_to_supabase([clean_user])
            except Exception as exc:
                logger.warning("Failed to sync updated pets to Supabase for %s: %s", clean_user, exc)

        parsed_result: Optional[Dict[str, Any]] = None
        for line in stdout_lines:
            idx = line.find("SYNC_RESULT_JSON:")
            if idx != -1:
                try:
                    parsed_result = json.loads(line[idx + 17 :])
                    break
                except json.JSONDecodeError:
                    pass

        await self.ws.broadcast("account-added", {"username": clean_user})

        if parsed_result:
            return parsed_result

        return {
            "success": code == 0,
            "username": clean_user,
            "message": "Đã đồng bộ xong" if code == 0 else "Không nhận được phản hồi từ máy chủ game",
            "pets": [],
            "count": 0,
        }

    # ------------------------------------------------------------------
    # Live Game Servers Fetching
    # ------------------------------------------------------------------
    async def fetch_live_servers(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch live servers from Pocket Games serverlist.php (matches gui_app/main.js)."""
        try:
            req_obj = [{"func": "GetServerList", "userid": "yuenan#1"}]
            req_json = json.dumps(req_obj, separators=(",", ":"))
            seq = 4
            sig = hashlib.md5(f"{seq}{req_json}{SERVERLIST_SALT}".encode("utf-8")).hexdigest()
            encoded_req = urllib.parse.quote(req_json, safe="")
            post_data = (
                f"bv=70%2E0%2E0&ptype=a&request={encoded_req}&seq={seq}"
                f"&session=&sig={sig}&sptype=spyuenan%5Fmd&version=73%2E0%2E0"
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    SERVERLIST_URL,
                    content=post_data.encode("utf-8"),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Dalvik/2.1.0",
                    },
                )

            if resp.status_code != 200:
                logger.warning("[ServerList] HTTP %s", resp.status_code)
                return None

            text = resp.text
            if text.startswith("0;"):
                text = text[2:]
            parsed = json.loads(text)
            infos = parsed[0].get("infos", []) if isinstance(parsed, list) and parsed else []
            if not isinstance(infos, list) or not infos:
                return None

            formatted: List[Dict[str, Any]] = []
            for s in infos:
                clean_tcp = str(s.get("tcp") or "").strip()
                if clean_tcp.startswith("/"):
                    clean_tcp = clean_tcp[1:]
                sid = str(s.get("id") or "").strip()
                if not sid:
                    continue
                formatted.append(
                    {
                        "id": sid,
                        "name": str(s.get("name") or f"Server {sid}"),
                        "tcp": clean_tcp,
                        "status": str(s.get("state") or "online"),
                    }
                )

            formatted.sort(
                key=lambda x: int(x["id"]) if x["id"].isdigit() else 0,
                reverse=True,
            )

            await self.storage.upsert_servers(formatted)
            return formatted
        except Exception as exc:
            logger.warning("[ServerList] Failed to fetch live servers: %s", exc)
            return None

    async def get_servers(self) -> List[Dict[str, Any]]:
        cached = await self.storage.get_all_servers()

        # Trigger throttled background sync (at most once every 60s)
        now = time.monotonic()
        if now - self._last_bg_server_refresh > 60.0:
            self._last_bg_server_refresh = now
            asyncio.create_task(self._background_refresh_servers(cached))

        return cached

    async def _background_refresh_servers(self, cached: List[Dict[str, Any]]) -> None:
        await asyncio.sleep(1.0)
        live = await self.fetch_live_servers()
        if live:
            has_changes = len(live) != len(cached) or (
                bool(live) and bool(cached) and live[0]["id"] != cached[0]["id"]
            )
            await self.ws.broadcast(
                "servers-updated",
                {"servers": live, "isNew": has_changes, "count": len(live)},
            )

    async def refresh_servers(self) -> Dict[str, Any]:
        live = await self.fetch_live_servers()
        if live:
            await self.ws.broadcast(
                "servers-updated",
                {"servers": live, "isNew": True, "count": len(live)},
            )
            return {"success": True, "count": len(live), "servers": live}
        return {"success": False, "message": "Không thể kết nối đến máy chủ game."}

    # ------------------------------------------------------------------
    # Concurrent Proxy Connectivity Check
    # ------------------------------------------------------------------
    async def check_proxies(
        self, proxies: Union[List[str], str], proxy_type: str = "http"
    ) -> Dict[str, Any]:
        raw_list = proxies.splitlines() if isinstance(proxies, str) else list(proxies or [])
        valid_entries = [
            str(p).strip()
            for p in raw_list
            if str(p).strip() and not str(p).strip().startswith("#")
        ]
        if not valid_entries:
            return {
                "success": False,
                "message": "Không có proxy hợp lệ để kiểm tra!",
                "total": 0,
                "alive": 0,
                "dead": 0,
                "results": [],
            }

        # Cap concurrent open sockets safely for Linux/Render ulimits while staying fast for 50+ proxies
        sem = asyncio.Semaphore(60)

        async def _check_one(raw: str) -> Dict[str, Any]:
            host, port = _parse_host_port(raw)
            if not host or port <= 0 or port > 65535:
                return {
                    "proxy": raw,
                    "alive": False,
                    "live": False,
                    "latency": 0,
                    "error": "Sai định dạng IP:Port",
                }

            async with sem:
                t0 = time.monotonic()
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=3.5
                    )
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
                    except Exception:
                        pass
                    return {
                        "proxy": raw,
                        "alive": True,
                        "live": True,
                        "latency": latency_ms,
                        "error": None,
                    }
                except asyncio.TimeoutError:
                    return {
                        "proxy": raw,
                        "alive": False,
                        "live": False,
                        "latency": 0,
                        "error": "Timeout 3.5s",
                    }
                except ConnectionRefusedError:
                    return {
                        "proxy": raw,
                        "alive": False,
                        "live": False,
                        "latency": 0,
                        "error": "Cổng đóng / Bị từ chối",
                    }
                except OSError as exc:
                    err_msg = "Không thể kết nối"
                    if "Name or service not known" in str(exc) or "getaddrinfo" in str(exc):
                        err_msg = "Không tìm thấy host"
                    elif "timed out" in str(exc).lower():
                        err_msg = "Hết thời gian chờ"
                    return {
                        "proxy": raw,
                        "alive": False,
                        "live": False,
                        "latency": 0,
                        "error": err_msg,
                    }
                except Exception as exc:
                    return {
                        "proxy": raw,
                        "alive": False,
                        "live": False,
                        "latency": 0,
                        "error": str(exc)[:100],
                    }

        results = await asyncio.gather(*(_check_one(entry) for entry in valid_entries))
        alive_count = sum(1 for r in results if r["alive"])
        dead_count = len(results) - alive_count
        return {
            "success": True,
            "total": len(results),
            "alive": alive_count,
            "dead": dead_count,
            "results": list(results),
        }

    # ------------------------------------------------------------------
    # Fetch Free Proxies from Proxifly
    # ------------------------------------------------------------------
    async def fetch_proxifly(
        self,
        country: str = "ALL",
        protocol: str = "http",
        quantity: int = 50,
        api_key: str = "",
    ) -> Dict[str, Any]:
        country = (country or "ALL").strip().upper()
        protocol = (protocol or "http").strip().lower()
        if protocol not in ("http", "socks5", "socks4"):
            protocol = "http"
        quantity = max(1, min(500, int(quantity or 50)))

        # 1. If API Key provided, query Proxifly REST API
        if api_key and api_key.strip():
            api_url = "https://api.proxifly.dev/get-proxy"
            payload: Dict[str, Any] = {
                "apiKey": api_key.strip(),
                "protocol": [protocol],
                "quantity": quantity,
                "https": True,
            }
            if country != "ALL":
                payload["country"] = [country]
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(api_url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        proxies = []
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "proxy" in item:
                                    p = item["proxy"]
                                    proxies.append(p.split("://")[1] if "://" in p else p)
                                elif isinstance(item, str):
                                    proxies.append(item.split("://")[1] if "://" in item else item)
                        elif isinstance(data, dict):
                            if "proxy" in data:
                                p = data["proxy"]
                                proxies.append(p.split("://")[1] if "://" in p else p)
                            elif "proxies" in data and isinstance(data["proxies"], list):
                                for p in data["proxies"]:
                                    proxies.append(p.split("://")[1] if "://" in p else p)
                        if proxies:
                            return {"success": True, "source": "api", "count": len(proxies), "proxies": proxies[:quantity]}
            except Exception as e:
                logger.warning(f"Proxifly API fetch failed, falling back to open repo: {e}")

        # 2. Fetch from Proxifly Open Free Proxy Repository
        urls = []
        if country != "ALL":
            urls.append(f"https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/{country}/data.txt")
            urls.append(f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/{country}/data.txt")
        else:
            urls.append(f"https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/{protocol}/data.txt")
            urls.append(f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/{protocol}/data.txt")

        raw_text = ""
        last_error = ""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and resp.text.strip():
                        raw_text = resp.text
                        break
                except Exception as exc:
                    last_error = str(exc)

        if not raw_text.strip():
            return {"success": False, "message": f"Không thể tải proxy từ Proxifly ({last_error or 'Kho dữ liệu trống'})", "proxies": []}

        # Parse & filter
        raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]
        parsed_proxies = []
        for line in raw_lines:
            if "://" in line:
                line_proto = line.split("://")[0].lower()
                clean_host_port = line.split("://")[1]
                if country != "ALL" and protocol in ("http", "socks5"):
                    if protocol == "http" and line_proto not in ("http", "https"):
                        continue
                    elif protocol == "socks5" and line_proto != "socks5":
                        continue
                parsed_proxies.append(clean_host_port)
            else:
                parsed_proxies.append(line)

        # Shuffle slightly to get fresh distribution if list is large
        import random
        random.shuffle(parsed_proxies)
        selected = parsed_proxies[:quantity]

        return {
            "success": True,
            "source": "free_repo",
            "country": country,
            "protocol": protocol,
            "total_available": len(parsed_proxies),
            "count": len(selected),
            "proxies": selected,
        }
