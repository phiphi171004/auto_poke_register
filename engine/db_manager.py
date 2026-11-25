import sqlite3
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict

def find_db_path() -> Path:
    # 1. Environment variable explicitly set by Web server / container
    env_db = os.environ.get("POKEMON_DB_PATH")
    if env_db:
        p_env = Path(env_db)
        p_env.parent.mkdir(parents=True, exist_ok=True)
        return p_env

    # 2. Default standalone web data directory: auto_register_web/data/pokemon_web.db
    web_root = Path(__file__).resolve().parent.parent
    default_db = web_root / "data" / "pokemon_web.db"
    default_db.parent.mkdir(parents=True, exist_ok=True)
    return default_db


DB_PATH = find_db_path()


class DatabaseManager:
    """Manages SQLite storage for Pokemon Master Auto (cross-platform web engine)"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else find_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            pass
        return conn

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tcp TEXT NOT NULL,
                status TEXT DEFAULT 'online',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pokedex (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                tier TEXT NOT NULL,
                type TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                token TEXT,
                user_id TEXT,
                zone_id TEXT,
                character_name TEXT,
                pets TEXT,
                raw TEXT,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            try:
                cursor.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'completed'")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE accounts ADD COLUMN lucky_sigh TEXT DEFAULT ''")
            except Exception:
                pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts(username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """)
            conn.commit()

    def save_account(self, result: dict) -> bool:
        """Insert or update a registered account in SQLite"""
        status = result.get("status")
        if not status:
            status = "completed" if result.get("success") else "failed"

        # Allow saving completed accounts and pending accounts
        if status not in ("completed", "pending_reward", "pending_draw") and not result.get("success"):
            return False

        acc = result.get("account", {})
        username = acc.get("username", "")
        password = acc.get("password", "")
        token = result.get("token", "")
        user_id = str(result.get("user_id", ""))
        zone_id = str(result.get("game_zone_id", ""))
        char_name = acc.get("character_name", "")
        pets = result.get("pets", [])
        pets_str = ",".join(pets) if pets else ""
        lucky_sigh = result.get("lucky_sigh", "") or ""
        raw = f"{username}:{password}:{token}:{user_id}:{zone_id}:{char_name}:[{pets_str}]"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO accounts (username, password, token, user_id, zone_id, character_name, pets, raw, status, lucky_sigh)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password=excluded.password,
                    token=excluded.token,
                    user_id=excluded.user_id,
                    zone_id=excluded.zone_id,
                    character_name=excluded.character_name,
                    pets=excluded.pets,
                    raw=excluded.raw,
                    status=excluded.status,
                    lucky_sigh=excluded.lucky_sigh;
                """, (username, password, token, user_id, zone_id, char_name, pets_str, raw, status, lucky_sigh))
                conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] Could not save account {username}: {e}")
            return False

    def get_all_accounts(self) -> List[Dict]:
        """Fetch all accounts from SQLite"""
        accounts = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, password, token, user_id, zone_id, character_name, pets, raw, status, lucky_sigh FROM accounts ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    pets = [p.strip() for p in row[6].split(",") if p.strip()] if row[6] else []
                    status_val = row[8] if len(row) > 8 and row[8] else "completed"
                    lucky_val = row[9] if len(row) > 9 and row[9] else ""
                    accounts.append({
                        "username": row[0],
                        "password": row[1],
                        "token": row[2],
                        "user_id": row[3],
                        "zone_id": row[4],
                        "character_name": row[5],
                        "pets": pets,
                        "raw": row[7],
                        "status": status_val,
                        "lucky_sigh": lucky_val
                    })
        except Exception as e:
            print(f"[DB Error] get_all_accounts: {e}")
        return accounts


    def get_account(self, username: str):
        """Fetch a single account by username"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT username, password, token, user_id, zone_id, character_name, pets, raw, status, lucky_sigh FROM accounts WHERE username = ?",
                    (username,)
                )
                row = cursor.fetchone()
                if row:
                    pets = [p.strip() for p in row[6].split(",") if p.strip()] if row[6] else []
                    status_val = row[8] if len(row) > 8 and row[8] else "completed"
                    lucky_val = row[9] if len(row) > 9 and row[9] else ""
                    return {
                        "username": row[0],
                        "password": row[1],
                        "token": row[2],
                        "user_id": row[3],
                        "zone_id": row[4],
                        "character_name": row[5],
                        "pets": pets,
                        "raw": row[7],
                        "status": status_val,
                        "lucky_sigh": lucky_val
                    }
        except Exception as e:
            print(f"[DB Error] get_account: {e}")
        return None

    def update_account_lucky_sigh(self, username: str, lucky_sigh: str) -> bool:
        """Update lucky stick reward for an account"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET lucky_sigh = ? WHERE username = ?",
                    (lucky_sigh, username)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] update_account_lucky_sigh: {e}")
            return False

    def update_account_pets(self, username: str, pets_str: str) -> bool:
        """Update pets string for an account and mark status completed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password, token, user_id, zone_id, character_name FROM accounts WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    pwd, tok, uid, zid, char = row
                    raw_str = f"{username}:{pwd}:{tok}:{uid}:{zid}:{char}:[{pets_str}]"
                    cursor.execute(
                        "UPDATE accounts SET pets = ?, raw = ?, status = 'completed' WHERE username = ?",
                        (pets_str, raw_str, username)
                    )
                else:
                    cursor.execute(
                        "UPDATE accounts SET pets = ?, status = 'completed' WHERE username = ?",
                        (pets_str, username)
                    )
                conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] update_account_pets: {e}")
            return False

    def delete_accounts(self, usernames: List[str]) -> bool:
        """Delete list of accounts by username in safe chunks"""
        clean_names = list(dict.fromkeys(str(u).strip() for u in usernames if u and str(u).strip()))
        if not clean_names:
            return True
        try:
            chunk_size = 900
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for idx in range(0, len(clean_names), chunk_size):
                    chunk = clean_names[idx:idx + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    cursor.execute(f"DELETE FROM accounts WHERE username IN ({placeholders})", chunk)
                conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] delete_accounts: {e}", file=sys.stderr)
            return False

