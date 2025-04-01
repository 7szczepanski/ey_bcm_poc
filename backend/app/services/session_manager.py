import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from jose import jwt, JWTError
from datetime import datetime, timedelta

# --- Configuration --- (Replace with environment variables in production)
COOKIE_SECRET_KEY = "a_very_secret_key_for_poc_only" # CHANGE THIS!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Session duration

APP_DIR = Path("/app") # Base directory inside container
SESSION_DIR = APP_DIR / "session_data" # Path should match what Docker creates
if not SESSION_DIR.exists():
    print(f"Creating session directory: {SESSION_DIR}")
    SESSION_DIR.mkdir(parents=True, exist_ok=True) # Ensure parent dirs exist

# --- Session Data Management ---
def create_session(session_id: str) -> bool:
    """Creates an empty session file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    print(f"Creating session file at: {session_file}")
    try:
        with open(session_file, 'w') as f:
            json.dump({}, f)
        print(f"Session file created successfully: {session_file.exists()}")
        return True
    except IOError as e:
        print(f"Error creating session file {session_file}: {e}")
        return False

def save_session_data(session_id: str, data: Dict[str, Any]) -> bool:
    """Saves data to the session file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    print(f"Saving session data to: {session_file}")
    try:
        # Consider file locking here for concurrent requests if needed
        with open(session_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Session data saved successfully: {session_file.exists()}")
        return True
    except IOError as e:
        print(f"Error saving session data to {session_file}: {e}")
        return False

def load_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads data from the session file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    print(f"Loading session data from: {session_file} (exists: {session_file.exists()})")
    if not session_file.exists():
        print(f"Session file does not exist: {session_file}")
        return None
    try:
        with open(session_file, 'r') as f:
            data = json.load(f)
            print(f"Session data loaded successfully for {session_id}: {data}")
            return data
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading session data from {session_file}: {e}")
        return None

def delete_session(session_id: str) -> bool:
    """Deletes a session file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    try:
        os.remove(session_file)
        return True
    except OSError:
        # Log error appropriately, file might not exist
        return False

# --- Session Cookie Management (Using JWT for signed sessions) ---
def create_session_cookie(session_id: str) -> str:
    """Creates a signed JWT containing the session_id."""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": session_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, COOKIE_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_session_cookie(session_cookie: Optional[str]) -> Optional[str]:
    """Verifies the JWT cookie and returns the session_id if valid."""
    if session_cookie is None:
        return None
    try:
        payload = jwt.decode(session_cookie, COOKIE_SECRET_KEY, algorithms=[ALGORITHM])
        session_id: str = payload.get("sub")
        if session_id is None:
            return None
        # Optional: Check if session file actually exists
        # if not (SESSION_DIR / f"{session_id}.json").exists():
        #     return None
        return session_id
    except JWTError:
        return None 