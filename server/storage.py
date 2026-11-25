"""
Unified persistence layer for Pokemon Auto Register Web.

Supports 3 storage backends (selected automatically by environment variables):
1. PostgreSQL / Supabase Transaction Pooler via `DATABASE_URL` (e.g.
   `postgresql://postgres.<ref>:<password>@aws-0-...pooler.supabase.com:6543/postgres`)
   using a bounded psycopg2 ThreadedConnectionPool (auto-creates schema on startup).
2. Supabase PostgREST HTTPS API via `SUPABASE_URL` + `SUPABASE_KEY`.
3. Local SQLite fallback at `auto_register_web/data/pokemon_web.db` when neither
   cloud backend is configured.

A local SQLite mirror is ALWAYS maintained for the engine subprocess
(`engine/main.py` & `game_socket_client.py`), with automatic bidirectional syncing
when running in remote (PostgreSQL / Supabase) mode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:  # pragma: no cover - optional when running SQLite/REST only
    psycopg2 = None  # type: ignore[assignment]

logger = logging.getLogger("pokemon_web.storage")

WEB_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = Path(__file__).resolve().parent
DATA_DIR = WEB_ROOT / "data"
SEED_DATA_PATH = SERVER_DIR / "seed_data.json"

# Load .env from auto_register_web/.env if present (never override explicit OS env)
load_dotenv(dotenv_path=WEB_ROOT / ".env", override=False)

_PLACEHOLDER_MARKERS = (
    "[YOUR-DATABASE-PASSWORD]",
    "[YOUR-PASSWORD]",
    "<YOUR-DATABASE-PASSWORD>",
    "<YOUR-PASSWORD>",
)


def _normalize_pets_list(pets_value: Any) -> List[str]:
    if isinstance(pets_value, list):
        return [str(p).strip() for p in pets_value if str(p).strip()]
    if isinstance(pets_value, str) and pets_value.strip():
        return [p.strip() for p in pets_value.split(",") if p.strip()]
    return []


def _pets_to_str(pets_value: Any) -> str:
    if isinstance(pets_value, list):
        return ",".join(str(p).strip() for p in pets_value if str(p).strip())
    return str(pets_value or "").strip()


def _format_timestamp(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat(sep=" ", timespec="seconds")
    return str(val)


def _format_account_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return exact account dict shape expected by gui_app/renderer.js."""
    return {
        "username": str(row.get("username") or ""),
        "password": str(row.get("password") or ""),
        "token": str(row.get("token") or ""),
        "user_id": str(row.get("user_id") or ""),
        "zone_id": str(row.get("zone_id") or ""),
        "character_name": str(row.get("character_name") or ""),
        "pets": _normalize_pets_list(row.get("pets")),
        "raw": str(row.get("raw") or ""),
        "status": str(row.get("status") or "completed"),
        "lucky_sigh": str(row.get("lucky_sigh") or ""),
        "created_at": _format_timestamp(row.get("created_at")),
    }


def _quote_postgrest_in_value(val: str) -> str:
    """Safely double-quote a string value for PostgREST `in.(...)` filter."""
    escaped = val.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _prepare_postgres_dsn(raw_dsn: str) -> str:
    """Normalize postgres:// URI and enforce sslmode=require for remote hosts."""
    dsn = raw_dsn.strip()
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://") :]

    parts = urlsplit(dsn)
    host = (parts.hostname or "").lower()
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))

    if host and host not in ("localhost", "127.0.0.1", "::1") and "sslmode" not in query_params:
        query_params["sslmode"] = "require"

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_params), parts.fragment))


def _redact_dsn(dsn: str) -> str:
    """Strip credentials before writing DSN to logs."""
    try:
        parts = urlsplit(dsn)
        user = parts.username or ""
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        auth = f"{user}:***@" if user else ""
        return f"{parts.scheme}://{auth}{host}{port}{parts.path}"
    except Exception:
        return "postgresql://***"


def _has_placeholder_password(dsn: str) -> bool:
    upper = dsn.upper()
    return any(marker.upper() in upper for marker in _PLACEHOLDER_MARKERS)


class StorageManager:
    """Unified PostgreSQL (Supabase Pooler) + Supabase PostgREST + Local SQLite manager."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        env_db = os.environ.get("POKEMON_DB_PATH", "").strip()
        if db_path is not None:
            self.db_path = Path(db_path)
        elif env_db:
            self.db_path = Path(env_db)
        else:
            self.db_path = DATA_DIR / "pokemon_web.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. PostgreSQL / Supabase Transaction Pooler (DATABASE_URL)
        raw_pg_dsn = (
            os.environ.get("DATABASE_URL", "").strip()
            or os.environ.get("SUPABASE_DB_URL", "").strip()
        )
        self.database_url: str = ""
        self.use_postgres: bool = False
        if raw_pg_dsn:
            if _has_placeholder_password(raw_pg_dsn):
                logger.warning(
                    "DATABASE_URL contains an unreplaced password placeholder (%s). "
                    "Replace it with your real Supabase database password; falling back for now.",
                    _redact_dsn(raw_pg_dsn),
                )
            elif psycopg2 is None:
                logger.warning(
                    "DATABASE_URL is configured but psycopg2-binary is not installed. "
                    "Run `pip install psycopg2-binary` to enable direct PostgreSQL/Supabase connection."
                )
            else:
                self.database_url = _prepare_postgres_dsn(raw_pg_dsn)
                self.use_postgres = True

        # 2. Supabase REST API fallback (SUPABASE_URL + SUPABASE_KEY)
        self.supabase_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "").strip()
        self.use_supabase_rest = (not self.use_postgres) and bool(
            self.supabase_url and self.supabase_key
        )

        # Unified flag used across task_runner / app
        self.use_supabase = self.use_postgres or self.use_supabase_rest
        if self.use_postgres:
            host = (urlsplit(self.database_url).hostname or "").lower()
            self.mode = "supabase" if "supabase" in host else "postgres"
        elif self.use_supabase_rest:
            self.mode = "supabase"
        else:
            self.mode = "sqlite"

        self._pg_pool: Optional[Any] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._seed_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._sqlite_lock = asyncio.Lock()

        self._init_sqlite_schema()
        self._seed_sqlite_if_empty()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def startup(self) -> None:
        if self.use_postgres:
            try:
                await asyncio.to_thread(self._init_pg_pool_and_schema)
                logger.info(
                    "Storage initialized in %s (PostgreSQL pool) mode (%s)",
                    self.mode.upper(),
                    _redact_dsn(self.database_url),
                )
                return
            except Exception as exc:
                logger.error(
                    "Failed to connect to PostgreSQL (%s): %s. Falling back to next storage backend.",
                    _redact_dsn(self.database_url),
                    exc,
                )
                self._close_pg_pool()
                self.use_postgres = False
                self.use_supabase_rest = bool(self.supabase_url and self.supabase_key)
                self.use_supabase = self.use_supabase_rest
                self.mode = "supabase" if self.use_supabase_rest else "sqlite"

        if self.use_supabase_rest and self._http is None:
            self._http = httpx.AsyncClient(
                base_url=f"{self.supabase_url}/rest/v1",
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(15.0, connect=8.0),
                limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
            )
            logger.info("Storage initialized in SUPABASE (REST) mode (%s)", self.supabase_url)
        else:
            logger.info("Storage initialized in SQLITE mode (%s)", self.db_path)

    async def shutdown(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        if self._pg_pool is not None:
            await asyncio.to_thread(self._close_pg_pool)

    # ------------------------------------------------------------------
    # PostgreSQL / Supabase Pooler Helpers
    # ------------------------------------------------------------------
    def _close_pg_pool(self) -> None:
        if self._pg_pool is not None:
            try:
                self._pg_pool.closeall()
            except Exception:
                pass
            self._pg_pool = None

    def _ensure_pg_pool(self) -> Any:
        if self._pg_pool is None:
            if psycopg2 is None:
                raise RuntimeError("psycopg2-binary is required for DATABASE_URL connections")
            max_conn = max(2, min(20, int(os.environ.get("PG_POOL_MAX", "10"))))
            self._pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=max_conn,
                dsn=self.database_url,
                connect_timeout=10,
            )
        return self._pg_pool

    @contextmanager
    def _pg_cursor(self, commit: bool = False, dict_cursor: bool = True) -> Iterator[Any]:
        pool = self._ensure_pg_pool()
        conn = pool.getconn()
        # Discard dead connections from idle pool timeouts before running query
        if getattr(conn, "closed", 0) != 0:
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = pool.getconn()

        cursor_factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        broken = False
        try:
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                yield cur
            if commit:
                conn.commit()
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            broken = True
            try:
                if getattr(conn, "closed", 0) == 0:
                    conn.rollback()
            except Exception:
                pass
            raise
        except Exception:
            try:
                if getattr(conn, "closed", 0) == 0:
                    conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                pool.putconn(conn, close=broken or getattr(conn, "closed", 0) != 0)
            except Exception:
                pass

    def _run_pg_with_retry(self, fn: Any) -> Any:
        try:
            return fn()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as first_err:
            logger.warning("PostgreSQL transient connection error, retrying once: %s", first_err)
            return fn()

    def _init_pg_pool_and_schema(self) -> None:
        def _create() -> None:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.accounts (
                        username TEXT PRIMARY KEY,
                        password TEXT NOT NULL,
                        token TEXT DEFAULT '',
                        user_id TEXT DEFAULT '',
                        zone_id TEXT DEFAULT '',
                        character_name TEXT DEFAULT '',
                        pets TEXT DEFAULT '',
                        raw TEXT DEFAULT '',
                        status TEXT DEFAULT 'completed',
                        lucky_sigh TEXT DEFAULT '',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_accounts_username ON public.accounts (username);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_accounts_status ON public.accounts (status);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_accounts_created_at ON public.accounts (created_at DESC);"
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.servers (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        tcp TEXT NOT NULL,
                        status TEXT DEFAULT 'online',
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.pokedex (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        tier TEXT NOT NULL,
                        type TEXT NOT NULL
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT DEFAULT ''
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.proxies (
                        proxy TEXT PRIMARY KEY,
                        proxy_type TEXT DEFAULT 'http',
                        status TEXT DEFAULT 'unchecked',
                        latency_ms INTEGER,
                        error TEXT DEFAULT '',
                        last_checked TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_proxies_status ON public.proxies (status);"
                )

        self._run_pg_with_retry(_create)

    def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=f"{self.supabase_url}/rest/v1",
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(15.0, connect=8.0),
                limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
            )
        return self._http

    # ------------------------------------------------------------------
    # SQLite Helpers
    # ------------------------------------------------------------------
    def _connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError:
            pass
        return conn

    def _init_sqlite_schema(self) -> None:
        with self._connect_sqlite() as conn:
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS servers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tcp TEXT NOT NULL,
                    status TEXT DEFAULT 'online',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS pokedex (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    tier TEXT NOT NULL,
                    type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    token TEXT DEFAULT '',
                    user_id TEXT DEFAULT '',
                    zone_id TEXT DEFAULT '',
                    character_name TEXT DEFAULT '',
                    pets TEXT DEFAULT '',
                    raw TEXT DEFAULT '',
                    status TEXT DEFAULT 'completed',
                    lucky_sigh TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts(username);
                CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS proxies (
                    proxy TEXT PRIMARY KEY,
                    proxy_type TEXT DEFAULT 'http',
                    status TEXT DEFAULT 'unchecked',
                    latency_ms INTEGER,
                    error TEXT DEFAULT '',
                    last_checked TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
                """
            )
            existing_cols = {
                row[1] for row in cur.execute("PRAGMA table_info(accounts)").fetchall()
            }
            if "status" not in existing_cols:
                cur.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'completed'")
            if "lucky_sigh" not in existing_cols:
                cur.execute("ALTER TABLE accounts ADD COLUMN lucky_sigh TEXT DEFAULT ''")
            conn.commit()

    def _load_seed_data(self) -> Dict[str, List[Dict[str, Any]]]:
        if self._seed_cache is not None:
            return self._seed_cache
        if SEED_DATA_PATH.exists():
            try:
                with open(SEED_DATA_PATH, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                self._seed_cache = {
                    "servers": data.get("servers", []),
                    "pokedex": data.get("pokedex", []),
                }
                return self._seed_cache
            except Exception as exc:
                logger.warning("Failed to load seed_data.json: %s", exc)
        self._seed_cache = {"servers": [], "pokedex": []}
        return self._seed_cache

    def _seed_sqlite_if_empty(self) -> None:
        seed = self._load_seed_data()
        with self._connect_sqlite() as conn:
            cur = conn.cursor()
            srv_count = cur.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
            if srv_count == 0 and seed["servers"]:
                cur.executemany(
                    """
                    INSERT OR IGNORE INTO servers (id, name, tcp, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            str(s["id"]),
                            str(s["name"]),
                            str(s["tcp"]),
                            str(s.get("status") or "online"),
                        )
                        for s in seed["servers"]
                    ],
                )

            dex_count = cur.execute("SELECT COUNT(*) FROM pokedex").fetchone()[0]
            if dex_count == 0 and seed["pokedex"]:
                cur.executemany(
                    """
                    INSERT OR IGNORE INTO pokedex (name, tier, type)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (str(p["name"]), str(p["tier"]), str(p["type"]))
                        for p in seed["pokedex"]
                    ],
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Servers Operations
    # ------------------------------------------------------------------
    def _sqlite_get_all_servers(self) -> List[Dict[str, Any]]:
        with self._connect_sqlite() as conn:
            rows = conn.execute(
                "SELECT id, name, tcp, status FROM servers ORDER BY CAST(id AS INTEGER) DESC"
            ).fetchall()
            return [
                {
                    "id": str(r["id"]),
                    "name": str(r["name"]),
                    "tcp": str(r["tcp"]),
                    "status": str(r["status"] or "online"),
                }
                for r in rows
            ]

    def _sqlite_upsert_servers(self, servers_list: List[Dict[str, Any]]) -> None:
        if not servers_list:
            return
        with self._connect_sqlite() as conn:
            conn.executemany(
                """
                INSERT INTO servers (id, name, tcp, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    tcp=excluded.tcp,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [
                    (
                        str(s["id"]),
                        str(s["name"]),
                        str(s["tcp"]),
                        str(s.get("status") or "online"),
                    )
                    for s in servers_list
                ],
            )
            conn.commit()

    def _pg_get_all_servers(self) -> List[Dict[str, Any]]:
        def _query() -> List[Dict[str, Any]]:
            with self._pg_cursor(commit=False, dict_cursor=True) as cur:
                cur.execute("SELECT id, name, tcp, status FROM public.servers")
                rows = cur.fetchall()
                normalized = [
                    {
                        "id": str(r.get("id", "")),
                        "name": str(r.get("name", "")),
                        "tcp": str(r.get("tcp", "")),
                        "status": str(r.get("status") or "online"),
                    }
                    for r in rows
                ]
                normalized.sort(
                    key=lambda x: int(x["id"]) if x["id"].isdigit() else 0,
                    reverse=True,
                )
                return normalized

        return self._run_pg_with_retry(_query)

    def _pg_upsert_servers(self, servers_list: List[Dict[str, Any]]) -> None:
        if not servers_list:
            return
        tuples = [
            (
                str(s["id"]),
                str(s["name"]),
                str(s["tcp"]),
                str(s.get("status") or "online"),
            )
            for s in servers_list
        ]

        def _write() -> None:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.servers (id, name, tcp, status)
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        tcp = EXCLUDED.tcp,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    """,
                    tuples,
                    page_size=500,
                )

        self._run_pg_with_retry(_write)

    async def get_all_servers(self) -> List[Dict[str, Any]]:
        if self.use_postgres:
            try:
                pg_rows = await asyncio.to_thread(self._pg_get_all_servers)
                if pg_rows:
                    await asyncio.to_thread(self._sqlite_upsert_servers, pg_rows)
                    return pg_rows
            except Exception as exc:
                logger.warning("PostgreSQL get_all_servers fallback to SQLite: %s", exc)
        elif self.use_supabase_rest:
            try:
                client = self._ensure_http()
                all_rows: List[Dict[str, Any]] = []
                page_size = 1000
                offset = 0
                while True:
                    resp = await client.get(
                        "/servers",
                        params={"select": "id,name,tcp,status"},
                        headers={"Range": f"{offset}-{offset + page_size - 1}"},
                    )
                    if resp.status_code in (200, 206):
                        batch = resp.json()
                        if not batch:
                            break
                        all_rows.extend(batch)
                        if len(batch) < page_size:
                            break
                        offset += page_size
                    else:
                        logger.warning(
                            "Supabase get_all_servers returned HTTP %s: %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        break

                if all_rows:
                    normalized = [
                        {
                            "id": str(r.get("id", "")),
                            "name": str(r.get("name", "")),
                            "tcp": str(r.get("tcp", "")),
                            "status": str(r.get("status") or "online"),
                        }
                        for r in all_rows
                    ]
                    normalized.sort(
                        key=lambda x: int(x["id"]) if x["id"].isdigit() else 0,
                        reverse=True,
                    )
                    await asyncio.to_thread(self._sqlite_upsert_servers, normalized)
                    return normalized
            except Exception as exc:
                logger.warning("Supabase get_all_servers fallback to SQLite: %s", exc)

        return await asyncio.to_thread(self._sqlite_get_all_servers)

    async def upsert_servers(self, servers_list: List[Dict[str, Any]]) -> None:
        if not servers_list:
            return

        # Always persist into local SQLite so engine/game_socket_client.py has latest TCP endpoints
        await asyncio.to_thread(self._sqlite_upsert_servers, servers_list)

        if self.use_postgres:
            try:
                await asyncio.to_thread(self._pg_upsert_servers, servers_list)
            except Exception as exc:
                logger.warning("PostgreSQL upsert_servers error: %s", exc)
        elif self.use_supabase_rest:
            client = self._ensure_http()
            chunk_size = 500
            for i in range(0, len(servers_list), chunk_size):
                chunk = [
                    {
                        "id": str(s["id"]),
                        "name": str(s["name"]),
                        "tcp": str(s["tcp"]),
                        "status": str(s.get("status") or "online"),
                    }
                    for s in servers_list[i : i + chunk_size]
                ]
                try:
                    resp = await client.post(
                        "/servers",
                        params={"on_conflict": "id"},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                        json=chunk,
                    )
                    if resp.status_code not in (200, 201, 204):
                        logger.warning(
                            "Supabase upsert_servers chunk %d failed (%s): %s",
                            i,
                            resp.status_code,
                            resp.text[:200],
                        )
                except Exception as exc:
                    logger.warning("Supabase upsert_servers error: %s", exc)

    # ------------------------------------------------------------------
    # Pokedex Operations
    # ------------------------------------------------------------------
    def _sqlite_get_all_pokedex(self) -> List[Dict[str, Any]]:
        with self._connect_sqlite() as conn:
            rows = conn.execute(
                "SELECT name, tier, type FROM pokedex ORDER BY id ASC"
            ).fetchall()
            return [
                {"name": str(r["name"]), "tier": str(r["tier"]), "type": str(r["type"])}
                for r in rows
            ]

    async def get_all_pokedex(self) -> List[Dict[str, Any]]:
        local_list = await asyncio.to_thread(self._sqlite_get_all_pokedex)
        if local_list:
            return local_list
        return list(self._load_seed_data().get("pokedex", []))

    # ------------------------------------------------------------------
    # Accounts Operations
    # ------------------------------------------------------------------
    def _sqlite_get_all_accounts(self) -> List[Dict[str, Any]]:
        with self._connect_sqlite() as conn:
            rows = conn.execute(
                """
                SELECT username, password, token, user_id, zone_id, character_name,
                       pets, raw, status, lucky_sigh, created_at
                FROM accounts
                ORDER BY created_at DESC
                """
            ).fetchall()
            return [_format_account_row(dict(r)) for r in rows]

    def _sqlite_get_accounts_by_usernames(self, usernames: Iterable[str]) -> List[Dict[str, Any]]:
        clean = list(dict.fromkeys(str(u).strip() for u in usernames if str(u or "").strip()))
        if not clean:
            return []
        result: List[Dict[str, Any]] = []
        with self._connect_sqlite() as conn:
            chunk_size = 900
            for i in range(0, len(clean), chunk_size):
                chunk = clean[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT username, password, token, user_id, zone_id, character_name,
                           pets, raw, status, lucky_sigh, created_at
                    FROM accounts
                    WHERE username IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
                result.extend(_format_account_row(dict(r)) for r in rows)
        return result

    def _sqlite_upsert_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        if not accounts:
            return
        with self._connect_sqlite() as conn:
            params = []
            for acc in accounts:
                username = str(acc.get("username") or "").strip()
                if not username:
                    continue
                password = str(acc.get("password") or "")
                token = str(acc.get("token") or "")
                user_id = str(acc.get("user_id") or "")
                zone_id = str(acc.get("zone_id") or "")
                character_name = str(acc.get("character_name") or "")
                pets_str = _pets_to_str(acc.get("pets"))
                raw = str(
                    acc.get("raw")
                    or f"{username}:{password}:{token}:{user_id}:{zone_id}:{character_name}:[{pets_str}]"
                )
                status = str(acc.get("status") or "completed")
                lucky_sigh = str(acc.get("lucky_sigh") or "")
                created_at = acc.get("created_at") or None
                params.append(
                    (
                        username,
                        password,
                        token,
                        user_id,
                        zone_id,
                        character_name,
                        pets_str,
                        raw,
                        status,
                        lucky_sigh,
                        created_at,
                    )
                )

            conn.executemany(
                """
                INSERT INTO accounts (
                    username, password, token, user_id, zone_id, character_name,
                    pets, raw, status, lucky_sigh, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                ON CONFLICT(username) DO UPDATE SET
                    password=excluded.password,
                    token=excluded.token,
                    user_id=excluded.user_id,
                    zone_id=excluded.zone_id,
                    character_name=excluded.character_name,
                    pets=excluded.pets,
                    raw=excluded.raw,
                    status=excluded.status,
                    lucky_sigh=excluded.lucky_sigh
                """,
                params,
            )
            conn.commit()

    def _sqlite_delete_accounts(self, usernames: List[str]) -> bool:
        clean = list(dict.fromkeys(str(u).strip() for u in usernames if str(u or "").strip()))
        if not clean:
            return True
        with self._connect_sqlite() as conn:
            chunk_size = 900
            for i in range(0, len(clean), chunk_size):
                chunk = clean[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                conn.execute(f"DELETE FROM accounts WHERE username IN ({placeholders})", chunk)
            conn.commit()
        return True

    def _pg_get_all_accounts(self) -> List[Dict[str, Any]]:
        def _query() -> List[Dict[str, Any]]:
            with self._pg_cursor(commit=False, dict_cursor=True) as cur:
                cur.execute(
                    """
                    SELECT username, password, token, user_id, zone_id, character_name,
                           pets, raw, status, lucky_sigh, created_at
                    FROM public.accounts
                    ORDER BY created_at DESC
                    """
                )
                return [_format_account_row(dict(r)) for r in cur.fetchall()]

        return self._run_pg_with_retry(_query)

    def _pg_upsert_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        tuples = []
        for acc in accounts:
            username = str(acc.get("username") or "").strip()
            if not username:
                continue
            password = str(acc.get("password") or "")
            token = str(acc.get("token") or "")
            user_id = str(acc.get("user_id") or "")
            zone_id = str(acc.get("zone_id") or "")
            char_name = str(acc.get("character_name") or "")
            pets_str = _pets_to_str(acc.get("pets"))
            raw = str(
                acc.get("raw")
                or f"{username}:{password}:{token}:{user_id}:{zone_id}:{char_name}:[{pets_str}]"
            )
            status = str(acc.get("status") or "completed")
            lucky_sigh = str(acc.get("lucky_sigh") or "")
            created_at = acc.get("created_at") or None
            tuples.append(
                (
                    username,
                    password,
                    token,
                    user_id,
                    zone_id,
                    char_name,
                    pets_str,
                    raw,
                    status,
                    lucky_sigh,
                    created_at,
                )
            )
        if not tuples:
            return

        def _write() -> None:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.accounts (
                        username, password, token, user_id, zone_id, character_name,
                        pets, raw, status, lucky_sigh, created_at
                    )
                    VALUES %s
                    ON CONFLICT (username) DO UPDATE SET
                        password = EXCLUDED.password,
                        token = EXCLUDED.token,
                        user_id = EXCLUDED.user_id,
                        zone_id = EXCLUDED.zone_id,
                        character_name = EXCLUDED.character_name,
                        pets = EXCLUDED.pets,
                        raw = EXCLUDED.raw,
                        status = EXCLUDED.status,
                        lucky_sigh = EXCLUDED.lucky_sigh
                    """,
                    tuples,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))",
                    page_size=200,
                )

        self._run_pg_with_retry(_write)

    def _pg_delete_accounts(self, clean: List[str]) -> None:
        def _delete() -> None:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                chunk_size = 500
                for i in range(0, len(clean), chunk_size):
                    chunk = clean[i : i + chunk_size]
                    cur.execute("DELETE FROM public.accounts WHERE username = ANY(%s)", (chunk,))

        self._run_pg_with_retry(_delete)

    def _pg_fetch_accounts_filtered(
        self, username: Optional[str] = None, pending_only: bool = False
    ) -> List[Dict[str, Any]]:
        def _query() -> List[Dict[str, Any]]:
            with self._pg_cursor(commit=False, dict_cursor=True) as cur:
                if username:
                    cur.execute(
                        """
                        SELECT username, password, token, user_id, zone_id, character_name,
                               pets, raw, status, lucky_sigh, created_at
                        FROM public.accounts
                        WHERE username = %s
                        """,
                        (username.strip(),),
                    )
                elif pending_only:
                    cur.execute(
                        """
                        SELECT username, password, token, user_id, zone_id, character_name,
                               pets, raw, status, lucky_sigh, created_at
                        FROM public.accounts
                        WHERE status IN ('pending_reward', 'pending_draw')
                        """
                    )
                else:
                    cur.execute(
                        """
                        SELECT username, password, token, user_id, zone_id, character_name,
                               pets, raw, status, lucky_sigh, created_at
                        FROM public.accounts
                        ORDER BY created_at DESC
                        """
                    )
                return [_format_account_row(dict(r)) for r in cur.fetchall()]

        return self._run_pg_with_retry(_query)

    async def get_all_accounts(self) -> List[Dict[str, Any]]:
        if self.use_postgres:
            try:
                return await asyncio.to_thread(self._pg_get_all_accounts)
            except Exception as exc:
                logger.error("PostgreSQL get_all_accounts error: %s", exc)
                return await asyncio.to_thread(self._sqlite_get_all_accounts)

        if self.use_supabase_rest:
            client = self._ensure_http()
            all_rows: List[Dict[str, Any]] = []
            page_size = 1000
            offset = 0
            try:
                while True:
                    resp = await client.get(
                        "/accounts",
                        params={
                            "select": "username,password,token,user_id,zone_id,character_name,pets,raw,status,lucky_sigh,created_at",
                            "order": "created_at.desc",
                        },
                        headers={"Range": f"{offset}-{offset + page_size - 1}"},
                    )
                    if resp.status_code in (200, 206):
                        batch = resp.json()
                        if not batch:
                            break
                        all_rows.extend(_format_account_row(r) for r in batch)
                        if len(batch) < page_size:
                            break
                        offset += page_size
                    else:
                        logger.error(
                            "Supabase get_all_accounts failed (%s): %s",
                            resp.status_code,
                            resp.text[:300],
                        )
                        raise RuntimeError(f"Supabase error HTTP {resp.status_code}")
                return all_rows
            except Exception as exc:
                logger.error("Supabase get_all_accounts error: %s", exc)
                return await asyncio.to_thread(self._sqlite_get_all_accounts)

        return await asyncio.to_thread(self._sqlite_get_all_accounts)

    async def upsert_accounts(self, accounts: List[Dict[str, Any]]) -> bool:
        if not accounts:
            return True

        await asyncio.to_thread(self._sqlite_upsert_accounts, accounts)

        if self.use_postgres:
            try:
                await asyncio.to_thread(self._pg_upsert_accounts, accounts)
                return True
            except Exception as exc:
                logger.error("PostgreSQL upsert_accounts exception: %s", exc)
                return False

        if not self.use_supabase_rest:
            return True

        client = self._ensure_http()
        ok = True
        chunk_size = 200
        for i in range(0, len(accounts), chunk_size):
            payload = []
            for acc in accounts[i : i + chunk_size]:
                username = str(acc.get("username") or "").strip()
                if not username:
                    continue
                pets_str = _pets_to_str(acc.get("pets"))
                password = str(acc.get("password") or "")
                token = str(acc.get("token") or "")
                user_id = str(acc.get("user_id") or "")
                zone_id = str(acc.get("zone_id") or "")
                char_name = str(acc.get("character_name") or "")
                raw = str(
                    acc.get("raw")
                    or f"{username}:{password}:{token}:{user_id}:{zone_id}:{char_name}:[{pets_str}]"
                )
                row_obj: Dict[str, Any] = {
                    "username": username,
                    "password": password,
                    "token": token,
                    "user_id": user_id,
                    "zone_id": zone_id,
                    "character_name": char_name,
                    "pets": pets_str,
                    "raw": raw,
                    "status": str(acc.get("status") or "completed"),
                    "lucky_sigh": str(acc.get("lucky_sigh") or ""),
                }
                if acc.get("created_at"):
                    row_obj["created_at"] = str(acc["created_at"])
                payload.append(row_obj)

            if not payload:
                continue

            try:
                resp = await client.post(
                    "/accounts",
                    params={"on_conflict": "username"},
                    headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=payload,
                )
                if resp.status_code not in (200, 201, 204):
                    logger.error(
                        "Supabase upsert_accounts failed (%s): %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    ok = False
            except Exception as exc:
                logger.error("Supabase upsert_accounts exception: %s", exc)
                ok = False
        return ok

    async def delete_accounts(self, usernames: List[str]) -> int:
        clean = list(dict.fromkeys(str(u).strip() for u in usernames if str(u or "").strip()))
        if not clean:
            return 0

        await asyncio.to_thread(self._sqlite_delete_accounts, clean)

        if self.use_postgres:
            await asyncio.to_thread(self._pg_delete_accounts, clean)
        elif self.use_supabase_rest:
            client = self._ensure_http()
            chunk_size = 100
            for i in range(0, len(clean), chunk_size):
                chunk = clean[i : i + chunk_size]
                in_clause = ",".join(_quote_postgrest_in_value(u) for u in chunk)
                resp = await client.delete(
                    "/accounts",
                    params={"username": f"in.({in_clause})"},
                    headers={"Prefer": "return=minimal"},
                )
                if resp.status_code not in (200, 204):
                    logger.error(
                        "Supabase delete_accounts failed (%s): %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    raise RuntimeError(f"Supabase delete failed (HTTP {resp.status_code})")

        return len(clean)

    # ------------------------------------------------------------------
    # Bidirectional Sync between Engine SQLite <-> Remote DB (Postgres / Supabase)
    # ------------------------------------------------------------------
    async def sync_local_accounts_to_supabase(
        self, usernames: Optional[Iterable[str]] = None
    ) -> int:
        """Push accounts written/updated by engine/main.py in local SQLite into Supabase/Postgres."""
        if not self.use_supabase:
            return 0
        if usernames is not None:
            rows = await asyncio.to_thread(self._sqlite_get_accounts_by_usernames, usernames)
        else:
            rows = await asyncio.to_thread(self._sqlite_get_all_accounts)

        if not rows:
            return 0
        await self.upsert_accounts(rows)
        return len(rows)

    async def hydrate_local_sqlite_from_supabase(
        self,
        username: Optional[str] = None,
        pending_only: bool = False,
    ) -> int:
        """
        Ensure accounts needed by engine/main.py (--resume / --sync-user) exist in
        local SQLite before spawning the subprocess.
        """
        if not self.use_supabase:
            return 0

        if self.use_postgres:
            try:
                rows = await asyncio.to_thread(
                    self._pg_fetch_accounts_filtered, username, pending_only
                )
            except Exception as exc:
                logger.warning("PostgreSQL hydrate_local_sqlite error: %s", exc)
                return 0
            if rows:
                await asyncio.to_thread(self._sqlite_upsert_accounts, rows)
            return len(rows)

        client = self._ensure_http()
        params: Dict[str, str] = {
            "select": "username,password,token,user_id,zone_id,character_name,pets,raw,status,lucky_sigh,created_at"
        }
        if username:
            params["username"] = f"eq.{username.strip()}"
        elif pending_only:
            params["status"] = "in.(pending_reward,pending_draw)"

        rows = []
        offset = 0
        page_size = 1000
        try:
            while True:
                resp = await client.get(
                    "/accounts",
                    params=params,
                    headers={"Range": f"{offset}-{offset + page_size - 1}"},
                )
                if resp.status_code in (200, 206):
                    batch = resp.json()
                    if not batch:
                        break
                    rows.extend(_format_account_row(r) for r in batch)
                    if len(batch) < page_size or username:
                        break
                    offset += page_size
                else:
                    logger.warning(
                        "Supabase hydrate_local_sqlite failed (%s): %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    break
        except Exception as exc:
            logger.warning("Supabase hydrate_local_sqlite error: %s", exc)
            return 0

        if rows:
            await asyncio.to_thread(self._sqlite_upsert_accounts, rows)
        return len(rows)

    # ------------------------------------------------------------------
    # Settings Operations
    # ------------------------------------------------------------------
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        if self.use_postgres:
            try:
                def _pg_read() -> Optional[str]:
                    with self._pg_cursor(commit=False, dict_cursor=True) as cur:
                        cur.execute(
                            "SELECT value FROM public.app_settings WHERE key = %s",
                            (key,),
                        )
                        row = cur.fetchone()
                        return str(row["value"]) if row else None

                val = await asyncio.to_thread(lambda: self._run_pg_with_retry(_pg_read))
                if val is not None:
                    return val
            except Exception as exc:
                logger.warning("PostgreSQL get_setting(%s) failed: %s", key, exc)
        elif self.use_supabase_rest:
            try:
                resp = await self._ensure_http().get(
                    "/app_settings",
                    params={"select": "value", "key": f"eq.{key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return str(data[0].get("value", ""))
            except Exception as exc:
                logger.warning("Supabase get_setting(%s) failed: %s", key, exc)

        def _read() -> Optional[str]:
            with self._connect_sqlite() as conn:
                row = conn.execute(
                    "SELECT value FROM app_settings WHERE key = ?", (key,)
                ).fetchone()
                return str(row["value"]) if row else default

        return await asyncio.to_thread(_read)

    async def set_setting(self, key: str, value: str) -> None:
        def _write() -> None:
            with self._connect_sqlite() as conn:
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (key, value),
                )
                conn.commit()

        await asyncio.to_thread(_write)

        if self.use_postgres:
            try:
                def _pg_write() -> None:
                    with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                        cur.execute(
                            """
                            INSERT INTO public.app_settings (key, value) VALUES (%s, %s)
                            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                            """,
                            (key, value),
                        )

                await asyncio.to_thread(lambda: self._run_pg_with_retry(_pg_write))
            except Exception as exc:
                logger.warning("PostgreSQL set_setting(%s) failed: %s", key, exc)
        elif self.use_supabase_rest:
            try:
                await self._ensure_http().post(
                    "/app_settings",
                    params={"on_conflict": "key"},
                    headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=[{"key": key, "value": value}],
                )
            except Exception as exc:
                logger.warning("Supabase set_setting(%s) failed: %s", key, exc)

    # ------------------------------------------------------------------
    # Proxies Table Operations
    # ------------------------------------------------------------------
    @staticmethod
    def _format_proxy_row(row: Dict[str, Any]) -> Dict[str, Any]:
        status = str(row.get("status") or "unchecked").lower()
        latency = row.get("latency_ms")
        if latency is None and "latency" in row:
            latency = row.get("latency")
        try:
            latency_int = int(latency) if latency is not None else None
        except (TypeError, ValueError):
            latency_int = None
        return {
            "proxy": str(row.get("proxy") or "").strip(),
            "proxy_type": str(row.get("proxy_type") or "http").lower(),
            "status": status if status in ("live", "dead", "unchecked") else "unchecked",
            "latency_ms": latency_int,
            "error": str(row.get("error") or ""),
            "last_checked": _format_timestamp(row.get("last_checked")),
            "updated_at": _format_timestamp(row.get("updated_at")),
        }

    @staticmethod
    def _clean_proxy_strings(proxies: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for raw in proxies:
            val = str(raw or "").strip()
            if not val or val.startswith("#") or val in seen:
                continue
            seen.add(val)
            out.append(val)
        return out

    def _sqlite_get_all_proxies(self) -> List[Dict[str, Any]]:
        with self._connect_sqlite() as conn:
            rows = conn.execute(
                """
                SELECT proxy, proxy_type, status, latency_ms, error, last_checked, updated_at
                FROM proxies
                ORDER BY
                    CASE status WHEN 'live' THEN 0 WHEN 'unchecked' THEN 1 ELSE 2 END ASC,
                    CASE WHEN latency_ms IS NULL THEN 999999 ELSE latency_ms END ASC,
                    proxy ASC
                """
            ).fetchall()
            return [self._format_proxy_row(dict(r)) for r in rows]

    def _sqlite_replace_proxies(self, clean_list: List[str], proxy_type: str = "http") -> int:
        ptype = (proxy_type or "http").strip().lower()
        if ptype not in ("http", "https", "socks5"):
            ptype = "http"
        with self._connect_sqlite() as conn:
            if not clean_list:
                conn.execute("DELETE FROM proxies")
                conn.commit()
                return 0

            # Remove proxies that are no longer in the user's list
            existing = {
                str(r[0]) for r in conn.execute("SELECT proxy FROM proxies").fetchall()
            }
            keep_set = set(clean_list)
            to_delete = list(existing - keep_set)
            if to_delete:
                chunk_size = 900
                for i in range(0, len(to_delete), chunk_size):
                    chunk = to_delete[i : i + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    conn.execute(f"DELETE FROM proxies WHERE proxy IN ({placeholders})", chunk)

            conn.executemany(
                """
                INSERT INTO proxies (proxy, proxy_type, status, updated_at)
                VALUES (?, ?, 'unchecked', CURRENT_TIMESTAMP)
                ON CONFLICT(proxy) DO UPDATE SET
                    proxy_type = excluded.proxy_type,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [(p, ptype) for p in clean_list],
            )
            conn.commit()
            return len(clean_list)

    def _sqlite_save_proxy_check_results(
        self, results: List[Dict[str, Any]], proxy_type: str = "http"
    ) -> int:
        ptype = (proxy_type or "http").strip().lower()
        if ptype not in ("http", "https", "socks5"):
            ptype = "http"
        rows_data = []
        seen: set[str] = set()
        for r in results:
            p = str(r.get("proxy") or "").strip()
            if not p or p in seen:
                continue
            seen.add(p)
            is_live = bool(r.get("alive") or r.get("live"))
            status = "live" if is_live else "dead"
            latency = r.get("latency")
            try:
                latency_val = int(latency) if (is_live and latency is not None) else None
            except (TypeError, ValueError):
                latency_val = None
            err = "" if is_live else str(r.get("error") or "Timeout")
            rows_data.append((p, ptype, status, latency_val, err))

        with self._connect_sqlite() as conn:
            conn.executemany(
                """
                INSERT INTO proxies (proxy, proxy_type, status, latency_ms, error, last_checked, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(proxy) DO UPDATE SET
                    proxy_type = excluded.proxy_type,
                    status = excluded.status,
                    latency_ms = excluded.latency_ms,
                    error = excluded.error,
                    last_checked = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows_data,
            )
            conn.commit()
        return len(rows_data)

    def _sqlite_clear_proxies(self) -> None:
        with self._connect_sqlite() as conn:
            conn.execute("DELETE FROM proxies")
            conn.commit()

    def _pg_get_all_proxies(self) -> List[Dict[str, Any]]:
        def _query() -> List[Dict[str, Any]]:
            with self._pg_cursor(commit=False, dict_cursor=True) as cur:
                cur.execute(
                    """
                    SELECT proxy, proxy_type, status, latency_ms, error, last_checked, updated_at
                    FROM public.proxies
                    ORDER BY
                        CASE status WHEN 'live' THEN 0 WHEN 'unchecked' THEN 1 ELSE 2 END ASC,
                        latency_ms ASC NULLS LAST,
                        proxy ASC
                    """
                )
                return [self._format_proxy_row(dict(r)) for r in cur.fetchall()]

        return self._run_pg_with_retry(_query)

    def _pg_replace_proxies(self, clean_list: List[str], proxy_type: str = "http") -> int:
        ptype = (proxy_type or "http").strip().lower()
        if ptype not in ("http", "https", "socks5"):
            ptype = "http"

        def _write() -> int:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                if not clean_list:
                    cur.execute("DELETE FROM public.proxies")
                    return 0

                cur.execute("DELETE FROM public.proxies WHERE NOT (proxy = ANY(%s))", (clean_list,))
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.proxies (proxy, proxy_type, status, updated_at)
                    VALUES %s
                    ON CONFLICT (proxy) DO UPDATE SET
                        proxy_type = EXCLUDED.proxy_type,
                        updated_at = NOW()
                    """,
                    [(p, ptype, "unchecked") for p in clean_list],
                    template="(%s, %s, %s, NOW())",
                    page_size=500,
                )
                return len(clean_list)

        return self._run_pg_with_retry(_write)

    def _pg_save_proxy_check_results(
        self, results: List[Dict[str, Any]], proxy_type: str = "http"
    ) -> int:
        ptype = (proxy_type or "http").strip().lower()
        if ptype not in ("http", "https", "socks5"):
            ptype = "http"
        tuples = []
        seen: set[str] = set()
        for r in results:
            p = str(r.get("proxy") or "").strip()
            if not p or p in seen:
                continue
            seen.add(p)
            is_live = bool(r.get("alive") or r.get("live"))
            status = "live" if is_live else "dead"
            latency = r.get("latency")
            try:
                latency_val = int(latency) if (is_live and latency is not None) else None
            except (TypeError, ValueError):
                latency_val = None
            err = "" if is_live else str(r.get("error") or "Timeout")
            tuples.append((p, ptype, status, latency_val, err))

        if not tuples:
            return 0

        def _write() -> int:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.proxies (
                        proxy, proxy_type, status, latency_ms, error, last_checked, updated_at
                    )
                    VALUES %s
                    ON CONFLICT (proxy) DO UPDATE SET
                        proxy_type = EXCLUDED.proxy_type,
                        status = EXCLUDED.status,
                        latency_ms = EXCLUDED.latency_ms,
                        error = EXCLUDED.error,
                        last_checked = NOW(),
                        updated_at = NOW()
                    """,
                    tuples,
                    template="(%s, %s, %s, %s, %s, NOW(), NOW())",
                    page_size=500,
                )
                return len(tuples)

        return self._run_pg_with_retry(_write)

    def _pg_clear_proxies(self) -> None:
        def _clear() -> None:
            with self._pg_cursor(commit=True, dict_cursor=False) as cur:
                cur.execute("DELETE FROM public.proxies")

        self._run_pg_with_retry(_clear)

    async def get_all_proxies(self) -> List[Dict[str, Any]]:
        if self.use_postgres:
            try:
                rows = await asyncio.to_thread(self._pg_get_all_proxies)
                return rows
            except Exception as exc:
                logger.error("PostgreSQL get_all_proxies error: %s", exc)
                return await asyncio.to_thread(self._sqlite_get_all_proxies)

        if self.use_supabase_rest:
            try:
                resp = await self._ensure_http().get(
                    "/proxies",
                    params={
                        "select": "proxy,proxy_type,status,latency_ms,error,last_checked,updated_at",
                        "order": "status.desc,latency_ms.asc.nullslast",
                    },
                )
                if resp.status_code in (200, 206):
                    rows = [self._format_proxy_row(r) for r in resp.json()]
                    rank = {"live": 0, "unchecked": 1, "dead": 2}
                    rows.sort(
                        key=lambda r: (
                            rank.get(r["status"], 1),
                            r["latency_ms"] if r["latency_ms"] is not None else 999999,
                            r["proxy"],
                        )
                    )
                    return rows
            except Exception as exc:
                logger.error("Supabase get_all_proxies error: %s", exc)

        return await asyncio.to_thread(self._sqlite_get_all_proxies)

    async def replace_proxies(self, proxies: Iterable[str], proxy_type: str = "http") -> int:
        clean = self._clean_proxy_strings(proxies)
        count = await asyncio.to_thread(self._sqlite_replace_proxies, clean, proxy_type)

        if self.use_postgres:
            try:
                await asyncio.to_thread(self._pg_replace_proxies, clean, proxy_type)
            except Exception as exc:
                logger.error("PostgreSQL replace_proxies error: %s", exc)
        elif self.use_supabase_rest:
            try:
                client = self._ensure_http()
                # Fetch existing to delete removed entries cleanly
                existing_resp = await client.get("/proxies", params={"select": "proxy"})
                existing = (
                    {str(r.get("proxy") or "") for r in existing_resp.json()}
                    if existing_resp.status_code == 200
                    else set()
                )
                to_delete = list(existing - set(clean))
                for i in range(0, len(to_delete), 100):
                    chunk = to_delete[i : i + 100]
                    in_clause = ",".join(_quote_postgrest_in_value(u) for u in chunk)
                    await client.delete(
                        "/proxies",
                        params={"proxy": f"in.({in_clause})"},
                        headers={"Prefer": "return=minimal"},
                    )
                ptype = (proxy_type or "http").strip().lower()
                for i in range(0, len(clean), 200):
                    payload = [{"proxy": p, "proxy_type": ptype} for p in clean[i : i + 200]]
                    await client.post(
                        "/proxies",
                        params={"on_conflict": "proxy"},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                        json=payload,
                    )
            except Exception as exc:
                logger.error("Supabase replace_proxies error: %s", exc)

        return count

    async def save_proxy_check_results(
        self, results: List[Dict[str, Any]], proxy_type: str = "http"
    ) -> int:
        if not results:
            return 0
        count = await asyncio.to_thread(
            self._sqlite_save_proxy_check_results, results, proxy_type
        )

        if self.use_postgres:
            try:
                await asyncio.to_thread(self._pg_save_proxy_check_results, results, proxy_type)
            except Exception as exc:
                logger.error("PostgreSQL save_proxy_check_results error: %s", exc)
        elif self.use_supabase_rest:
            try:
                client = self._ensure_http()
                now_iso = datetime.utcnow().isoformat() + "Z"
                ptype = (proxy_type or "http").strip().lower()
                payload = []
                for r in results:
                    p = str(r.get("proxy") or "").strip()
                    if not p:
                        continue
                    is_live = bool(r.get("alive") or r.get("live"))
                    payload.append(
                        {
                            "proxy": p,
                            "proxy_type": ptype,
                            "status": "live" if is_live else "dead",
                            "latency_ms": int(r["latency"]) if (is_live and r.get("latency") is not None) else None,
                            "error": "" if is_live else str(r.get("error") or "Timeout"),
                            "last_checked": now_iso,
                            "updated_at": now_iso,
                        }
                    )
                for i in range(0, len(payload), 200):
                    await client.post(
                        "/proxies",
                        params={"on_conflict": "proxy"},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                        json=payload[i : i + 200],
                    )
            except Exception as exc:
                logger.error("Supabase save_proxy_check_results error: %s", exc)

        return count

    async def clear_proxies(self) -> None:
        await asyncio.to_thread(self._sqlite_clear_proxies)
        if self.use_postgres:
            try:
                await asyncio.to_thread(self._pg_clear_proxies)
            except Exception as exc:
                logger.error("PostgreSQL clear_proxies error: %s", exc)
        elif self.use_supabase_rest:
            try:
                await self._ensure_http().delete(
                    "/proxies",
                    params={"proxy": "neq."},
                    headers={"Prefer": "return=minimal"},
                )
            except Exception as exc:
                logger.error("Supabase clear_proxies error: %s", exc)
