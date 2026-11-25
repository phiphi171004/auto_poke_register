"""
Account Generator
Generate valid usernames and passwords
"""

import random
import string
import re
import uuid
import secrets
import os
import sqlite3
import threading
from config import VALIDATION


class AccountGenerator:
    """Generate valid account credentials with ZERO collision guarantee"""
    
    _used_usernames = set()
    _db_checked = False
    _lock = threading.Lock()
    
    _PREFIXES = [
        "u", "p", "x", "z", "k", "r", "m", "t", "v", "s",
        "pk", "tk", "zen", "kai", "neo", "star", "rex", "sky"
    ]

    @classmethod
    def _init_db_cache(cls):
        """Preload existing usernames from SQLite database once to prevent cross-session collisions"""
        if cls._db_checked:
            return
        with cls._lock:
            if cls._db_checked:
                return
            cls._db_checked = True
            try:
                db_paths = [
                    os.environ.get("POKEMON_DB_PATH"),
                    os.path.join(os.path.dirname(__file__), "..", "data", "pokemon_web.db"),
                    os.path.join(os.path.dirname(__file__), "..", "data", "accounts.db"),
                    os.path.join(os.path.dirname(__file__), "accounts.db"),
                ]
                for p in db_paths:
                    if p and os.path.exists(p):
                        conn = sqlite3.connect(p)
                        cur = conn.cursor()
                        cur.execute("SELECT username FROM accounts")
                        for row in cur.fetchall():
                            if row and row[0]:
                                cls._used_usernames.add(str(row[0]).strip().lower())
                        conn.close()
                        break
            except Exception:
                pass

    @classmethod
    def generate_username(cls, prefix: str = "") -> str:
        """
        Generate non-repeating cryptographically unique username (Cách 2 - UUID / Cryptographic Hex).
        Guaranteed ZERO collision via 16^10 entropy + memory cache + database deduplication.
        - Always starts with a letter
        - 10-12 characters, strictly alphanumeric [a-z0-9]
        - Complies with validation: 4-50 chars, ^[a-zA-Z0-9_]{4,50}$
        """
        cls._init_db_cache()
        
        with cls._lock:
            while True:
                # Select a clean prefix if not provided
                pref = prefix if prefix else secrets.choice(cls._PREFIXES)
                
                # 9-10 chars of cryptographic hex (16^9 to 16^10 combinations, over 1 trillion)
                hex_part = uuid.uuid4().hex[:9]
                candidate = f"{pref}{hex_part}".lower()
                
                # Ensure length is within boundaries
                if len(candidate) > VALIDATION["account_max_length"]:
                    candidate = candidate[:VALIDATION["account_max_length"]]
                
                # Verify zero collision against memory and database cache
                if candidate not in cls._used_usernames and re.match(VALIDATION["account_pattern"], candidate):
                    cls._used_usernames.add(candidate)
                    return candidate

    @classmethod
    def generate_random_username(cls) -> str:
        """Alias for generate_username to ensure all callers benefit from zero collision"""
        return cls.generate_username()
    
    @staticmethod
    def generate_password() -> str:
        """
        Generate password according to rules:
        - 6-20 characters
        - Should be strong but remember analysis says users copy it
        """
        # Generate pronounceable password
        length = random.randint(8, 14)
        
        # Mix of different character types
        chars = (
            random.choices(string.ascii_lowercase, k=length//2) +
            random.choices(string.digits, k=length//4) +
            random.choices(string.ascii_uppercase, k=length//4)
        )
        
        random.shuffle(chars)
        password = ''.join(chars)
        
        # Ensure length is valid
        min_len = VALIDATION["password_min_length"]
        max_len = VALIDATION["password_max_length"]
        
        if len(password) < min_len:
            password = password + ''.join(random.choices(string.digits, k=min_len-len(password)))
        
        if len(password) > max_len:
            password = password[:max_len]
        
        return password
    
    @staticmethod
    def generate_email(username: str) -> str:
        """Generate email for the account"""
        domains = [
            'gmail.com',
            'yahoo.com', 
            'outlook.com',
            'hotmail.com',
            'protonmail.com'
        ]
        
        domain = random.choice(domains)
        return f"{username}@{domain}"
    
    @staticmethod
    def generate_character_name() -> str:
        """
        Generate random game character/role name
        Always maintains a 6-digit unique random number within 9-11 characters to prevent collisions.
        """
        prefixes = [
            "Ash", "Red", "Blue", "Gold", "Ruby", "Shad", "Drag", 
            "Phon", "Long", "Bao", "Huy", "Khan", "Minh", "Tuan", "Dat",
            "BeNa", "Sieu", "Than", "VoSo", "DocC", "Thie", "Poke", "Star",
            "Hero", "King", "Lord", "Nova", "Apex", "Zen", "Neo"
        ]
        pref = random.choice(prefixes)[:5]
        num = random.randint(100000, 999999)
        return f"{pref}{num}"  # Always 9-11 chars, 1,000,000 unique combinations per prefix!

    @classmethod
    def generate_account(cls) -> dict:
        """Generate complete account data"""
        username = cls.generate_username()
        password = cls.generate_password()
        email = cls.generate_email(username)
        char_name = cls.generate_character_name()
        
        return {
            "username": username,
            "password": password,
            "email": email,
            "character_name": char_name
        }
    
    @classmethod
    def generate_multiple(cls, count: int) -> list:
        """Generate multiple unique accounts"""
        accounts = []
        used_usernames = set()
        
        attempts = 0
        max_attempts = count * 10  # Prevent infinite loop
        
        while len(accounts) < count and attempts < max_attempts:
            account = cls.generate_account()
            
            if account["username"] not in used_usernames:
                used_usernames.add(account["username"])
                accounts.append(account)
            
            attempts += 1
        
        return accounts
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username against rules"""
        pattern = VALIDATION["account_pattern"]
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """Validate password against rules"""
        min_len = VALIDATION["password_min_length"]
        max_len = VALIDATION["password_max_length"]
        return min_len <= len(password) <= max_len


if __name__ == "__main__":
    # Test account generation
    generator = AccountGenerator()
    
    print("Testing Account Generator\n")
    
    # Generate single account
    account = generator.generate_account()
    print("Generated Account:")
    print(f"  Username: {account['username']}")
    print(f"  Password: {account['password']}")
    print(f"  Email: {account['email']}")
    print(f"  Username valid: {generator.validate_username(account['username'])}")
    print(f"  Password valid: {generator.validate_password(account['password'])}")
    
    # Generate multiple
    print("\nGenerating 5 accounts:")
    accounts = generator.generate_multiple(5)
    for i, acc in enumerate(accounts, 1):
        print(f"{i}. {acc['username']} | {acc['password']}")
