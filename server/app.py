"""
FastAPI backend server for Pokemon Auto Register Web.

Serves:
- REST API matching gui_app/main.js IPC contracts
- WebSocket /ws for real-time engine logs, task status, accounts & servers events
- Optional PIN protection (ACCESS_PIN env var)
- Static frontend files from auto_register_web/frontend/
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .storage import WEB_ROOT, StorageManager
from .task_runner import ConnectionManager, TaskRunner

load_dotenv(dotenv_path=WEB_ROOT / ".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("pokemon_web.app")

FRONTEND_DIR = WEB_ROOT / "frontend"
_SAFE_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-@]{1,100}$")


def _get_access_pin() -> str:
    return os.environ.get("ACCESS_PIN", "").strip()


def _verify_pin_value(candidate: Optional[str]) -> bool:
    expected = _get_access_pin()
    if not expected:
        return True
    if not candidate:
        return False
    return hmac.compare_digest(candidate.strip(), expected)


def _validate_username_param(username: str) -> str:
    cleaned = (username or "").strip()
    if not cleaned or ".." in cleaned or "/" in cleaned or "\\" in cleaned or not _SAFE_USERNAME_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="Tên tài khoản không hợp lệ")
    return cleaned


async def require_pin(x_access_pin: Optional[str] = Header(default=None, alias="X-Access-Pin")) -> None:
    if not _verify_pin_value(x_access_pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã PIN không hợp lệ hoặc chưa được cung cấp",
        )


# ------------------------------------------------------------------
# Pydantic Request Models
# ------------------------------------------------------------------
class PinVerifyRequest(BaseModel):
    pin: str = Field(default="", max_length=128)


class StartTaskRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100000000)
    zone: Union[str, int] = Field(default="2160")
    delayMin: float = Field(default=1.5, ge=0.0, le=300.0)
    delayMax: float = Field(default=3.0, ge=0.0, le=300.0)
    maxPerMinute: int = Field(default=100, ge=1, le=1000000)
    visitorUpgrade: bool = True
    claimMail: bool = True
    autoDraw: bool = True
    customUsername: Optional[str] = Field(default=None, max_length=64)
    customPassword: Optional[str] = Field(default=None, max_length=64)
    autoIncrementUsername: bool = True
    threads: int = Field(default=1, ge=1, le=500)
    networkMode: str = Field(default="direct")
    proxyType: str = Field(default="http")
    proxies: Union[List[str], str] = Field(default_factory=list)

    @field_validator("networkMode")
    @classmethod
    def _check_network_mode(cls, v: str) -> str:
        val = (v or "direct").strip().lower()
        return val if val in ("direct", "proxy") else "direct"

    @field_validator("proxyType")
    @classmethod
    def _check_proxy_type(cls, v: str) -> str:
        val = (v or "http").strip().lower()
        return val if val in ("http", "https", "socks5") else "http"


class ResumeTaskRequest(BaseModel):
    username: Optional[str] = Field(default=None, max_length=100)
    threads: int = Field(default=1, ge=1, le=100)
    proxies: Union[List[str], str] = Field(default_factory=list)
    networkMode: str = Field(default="direct")
    proxyType: str = Field(default="socks5")


class BulkDeleteRequest(BaseModel):
    usernames: List[str] = Field(default_factory=list, max_length=50000)


class ProxyCheckRequest(BaseModel):
    proxies: Union[List[str], str] = Field(default_factory=list)
    type: str = Field(default="http")


class FetchProxiflyRequest(BaseModel):
    country: str = Field(default="ALL")
    protocol: str = Field(default="http")
    quantity: int = Field(default=50)
    apiKey: str = Field(default="")


# ------------------------------------------------------------------
# App & Shared Singletons
# ------------------------------------------------------------------
storage = StorageManager()
ws_manager = ConnectionManager()
task_runner = TaskRunner(storage=storage, ws_manager=ws_manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await storage.startup()
    logger.info(
        "Pokemon Auto Register Web started (storage=%s, pin_required=%s)",
        storage.mode,
        bool(_get_access_pin()),
    )
    try:
        yield
    finally:
        await task_runner.shutdown()
        await storage.shutdown()
        logger.info("Pokemon Auto Register Web shut down cleanly")


app = FastAPI(
    title="Pokemon Auto Register Web",
    version="1.0.0",
    lifespan=lifespan,
)


# ------------------------------------------------------------------
# Health & Auth Endpoints (exempt from X-Access-Pin)
# ------------------------------------------------------------------
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "storage": storage.mode,
        "running": task_runner.is_running,
        "pin_required": bool(_get_access_pin()),
    }


@app.get("/api/config/status")
async def get_config_status() -> Dict[str, Any]:
    return {
        "storage": storage.mode,
        "running": task_runner.is_running,
        "pin_required": bool(_get_access_pin()),
    }


@app.post("/api/auth/verify")
async def verify_pin(body: PinVerifyRequest) -> JSONResponse:
    if _verify_pin_value(body.pin):
        return JSONResponse(status_code=200, content={"ok": True})
    return JSONResponse(
        status_code=401,
        content={"ok": False, "detail": "Mã PIN không chính xác"},
    )


# ------------------------------------------------------------------
# Task Endpoints
# ------------------------------------------------------------------
@app.post("/api/task/start", dependencies=[Depends(require_pin)])
async def api_start_task(config: StartTaskRequest) -> Dict[str, Any]:
    payload = config.model_dump()
    if payload.get("networkMode") == "proxy":
        raw_proxies = payload.get("proxies") or []
        proxy_lines = (
            raw_proxies.splitlines() if isinstance(raw_proxies, str) else list(raw_proxies)
        )
        if any(str(p).strip() and not str(p).strip().startswith("#") for p in proxy_lines):
            await storage.replace_proxies(proxy_lines, proxy_type=payload.get("proxyType") or "http")
    return await task_runner.start_task(payload)


@app.post("/api/task/stop", dependencies=[Depends(require_pin)])
async def api_stop_task() -> Dict[str, Any]:
    return await task_runner.stop_task()


@app.post("/api/task/resume", dependencies=[Depends(require_pin)])
async def api_resume_task(body: Optional[ResumeTaskRequest] = None) -> Dict[str, Any]:
    payload = body.model_dump() if body is not None else {}
    return await task_runner.resume_pending(payload)


# ------------------------------------------------------------------
# Server & Pokedex Endpoints
# ------------------------------------------------------------------
@app.get("/api/servers", dependencies=[Depends(require_pin)])
async def api_get_servers() -> List[Dict[str, Any]]:
    return await task_runner.get_servers()


@app.post("/api/servers/refresh", dependencies=[Depends(require_pin)])
async def api_refresh_servers() -> Dict[str, Any]:
    return await task_runner.refresh_servers()


@app.get("/api/pokedex", dependencies=[Depends(require_pin)])
async def api_get_pokedex() -> List[Dict[str, Any]]:
    return await storage.get_all_pokedex()


# ------------------------------------------------------------------
# Accounts Endpoints
# ------------------------------------------------------------------
@app.get("/api/accounts", dependencies=[Depends(require_pin)])
async def api_get_accounts() -> List[Dict[str, Any]]:
    return await storage.get_all_accounts()


@app.delete("/api/accounts/{username}", dependencies=[Depends(require_pin)])
async def api_delete_account(username: str) -> Dict[str, Any]:
    clean_user = _validate_username_param(username)
    try:
        deleted = await storage.delete_accounts([clean_user])
        return {"success": True, "deleted": deleted, "username": clean_user}
    except Exception as exc:
        logger.error("Failed to delete account %s: %s", clean_user, exc)
        raise HTTPException(status_code=500, detail="Không thể xóa tài khoản khỏi CSDL")


@app.post("/api/accounts/bulk-delete", dependencies=[Depends(require_pin)])
async def api_bulk_delete_accounts(body: BulkDeleteRequest) -> Dict[str, Any]:
    try:
        deleted = await storage.delete_accounts(body.usernames)
        return {"success": True, "deleted": deleted}
    except Exception as exc:
        logger.error("Failed to bulk delete accounts: %s", exc)
        raise HTTPException(status_code=500, detail="Không thể xóa danh sách tài khoản khỏi CSDL")


@app.post("/api/accounts/{username}/sync-pets", dependencies=[Depends(require_pin)])
async def api_sync_account_pets(username: str) -> Dict[str, Any]:
    clean_user = _validate_username_param(username)
    return await task_runner.sync_account_pets(clean_user)


# ------------------------------------------------------------------
# Proxy Storage & Checker Endpoints
# ------------------------------------------------------------------
@app.get("/api/proxies", dependencies=[Depends(require_pin)])
async def api_get_proxies() -> Dict[str, Any]:
    rows = await storage.get_all_proxies()
    alive_count = sum(1 for r in rows if r["status"] == "live")
    dead_count = sum(1 for r in rows if r["status"] == "dead")
    proxy_type = rows[0]["proxy_type"] if rows else "http"
    return {
        "success": True,
        "proxies": rows,
        "proxyType": proxy_type,
        "total": len(rows),
        "alive": alive_count,
        "dead": dead_count,
    }


@app.put("/api/proxies", dependencies=[Depends(require_pin)])
async def api_save_proxies(body: ProxyCheckRequest) -> Dict[str, Any]:
    raw_list = body.proxies.splitlines() if isinstance(body.proxies, str) else list(body.proxies or [])
    count = await storage.replace_proxies(raw_list, proxy_type=body.type)
    return {"success": True, "count": count}


@app.delete("/api/proxies", dependencies=[Depends(require_pin)])
async def api_clear_proxies() -> Dict[str, Any]:
    await storage.clear_proxies()
    return {"success": True}


@app.post("/api/proxies/check", dependencies=[Depends(require_pin)])
async def api_check_proxies(body: ProxyCheckRequest) -> Dict[str, Any]:
    res = await task_runner.check_proxies(proxies=body.proxies, proxy_type=body.type)
    if res.get("success") and res.get("results"):
        # Sync current checked list and persist live/dead/latency to `proxies` table
        raw_list = body.proxies.splitlines() if isinstance(body.proxies, str) else list(body.proxies or [])
        await storage.replace_proxies(raw_list, proxy_type=body.type)
        saved_count = await storage.save_proxy_check_results(res["results"], proxy_type=body.type)
        res["saved"] = saved_count
    return res


@app.post("/api/proxies/fetch-proxifly", dependencies=[Depends(require_pin)])
async def api_fetch_proxifly(body: FetchProxiflyRequest) -> Dict[str, Any]:
    return await task_runner.fetch_proxifly(
        country=body.country,
        protocol=body.protocol,
        quantity=body.quantity,
        api_key=body.apiKey,
    )


# ------------------------------------------------------------------
# WebSocket Endpoint
# ------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    pin: Optional[str] = Query(default=None),
) -> None:
    if not _verify_pin_value(pin):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(websocket)
    try:
        # Send initial task-status immediately upon connect
        await ws_manager.send_personal(
            websocket,
            "task-status",
            {"running": task_runner.is_running, "mode": task_runner.current_mode},
        )
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ------------------------------------------------------------------
# Static Frontend Mount (registered last so /api/* and /ws take precedence)
# ------------------------------------------------------------------
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)
