from passlib.context import CryptContext
from typing import Dict, Optional
from pathlib import Path

# Correct path inside the container where users.txt is mounted
USERS_FILE = Path("/app/users.txt")
if not USERS_FILE.exists():
    # Try alternate paths based on Docker configuration
    alt_paths = [
        Path("users.txt"),  # Current directory
        Path("../users.txt"),  # One level up
        Path("/backend/users.txt"),  # Direct mount
    ]
    for alt_path in alt_paths:
        if alt_path.exists():
            USERS_FILE = alt_path
            print(f"Found users.txt at {USERS_FILE}")
            break
    else:
        print(f"Warning: users.txt not found in any expected location. Startup may fail.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_users_cache: Optional[Dict[str, str]] = None

def get_users_from_file() -> Dict[str, str]:
    """Reads users from users.txt (username:password_hash). Caches result."""
    global _users_cache
    if _users_cache is not None:
        return _users_cache

    users = {}
    if not USERS_FILE.exists():
        print(f"Error: Users file not found at {USERS_FILE}. Check Docker volume mount.")
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    username, password = line.split(':', 1)
                    # If storing plain text (less secure PoC):
                    # users[username.strip()] = password.strip()
                    # If storing hashed passwords (better PoC):
                    # Assume format username:hashed_password in file
                    # users[username.strip()] = password.strip()
                    # --- For this implementation, we'll verify plain text for simplicity as per initial request --- 
                    users[username.strip()] = password.strip() # Keep plain for now
        print(f"Loaded {len(users)} users from {USERS_FILE}")
    except IOError as e:
        print(f"Error reading {USERS_FILE}: {e}")
        # In a real app, handle this more robustly

    _users_cache = users
    return users

def verify_password(plain_password: str, stored_password: str) -> bool:
    """Verifies a plain password against the stored password (plain text for this PoC)."""
    # If using hashed passwords with passlib:
    # return pwd_context.verify(plain_password, hashed_password)
    # --- Plain text comparison for this PoC --- 
    return plain_password == stored_password

# --- Helper for hashing (if needed during setup/user add) ---
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Example usage for creating a user file with hashed passwords:
# if __name__ == "__main__":
#     print(f"testuser:{get_password_hash('password123')}") 