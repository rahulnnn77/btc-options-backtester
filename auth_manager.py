import os
import json
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Tuple

USER_DB_FILE = os.path.join(os.path.dirname(__file__), "data", "users_auth.json")


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a password with a cryptographic salt using PBKDF2."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return key.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a plain password against the stored salt and hash."""
    calc_hash, _ = _hash_password(password, salt)
    return secrets.compare_digest(calc_hash, stored_hash)


def _load_users() -> Dict[str, dict]:
    """Load users from the JSON database file or initialize defaults."""
    os.makedirs(os.path.dirname(USER_DB_FILE), exist_ok=True)
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Initialize default admin accounts
    users = {}
    default_pwd = os.getenv("ADMIN_PASSWORD", "DeltaAdmin2026!")

    for admin_user in ["admin", "rahul"]:
        pwd_hash, salt = _hash_password(default_pwd)
        users[admin_user] = {
            "username": admin_user,
            "password_hash": pwd_hash,
            "salt": salt,
            "role": "admin",
            "status": "approved",
            "note": "Super Admin Account",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
        }

    _save_users(users)
    return users


def _save_users(users: Dict[str, dict]) -> None:
    """Persist users to disk."""
    os.makedirs(os.path.dirname(USER_DB_FILE), exist_ok=True)
    with open(USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def authenticate_user(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Authenticate a user.
    Returns: (success: bool, message: str, user_data: Optional[dict])
    """
    users = _load_users()
    uname = username.strip().lower()

    if uname not in users:
        return False, "User does not exist.", None

    user = users[uname]
    if not _verify_password(password, user["password_hash"], user["salt"]):
        return False, "Incorrect password.", None

    status = user.get("status", "pending")
    if status == "pending":
        return False, "Your account is pending Admin approval. Please contact the administrator.", None
    elif status == "rejected":
        return False, "Access declined by Admin.", None
    elif status != "approved":
        return False, f"Account status: {status}. Access not allowed.", None

    # Update last login timestamp
    user["last_login"] = datetime.utcnow().isoformat()
    _save_users(users)

    return True, "Login successful!", user


def register_user(username: str, password: str, note: str = "") -> Tuple[bool, str]:
    """Register a new user account with 'pending' status."""
    users = _load_users()
    uname = username.strip().lower()

    if not uname:
        return False, "Username cannot be empty."
    if len(uname) < 3:
        return False, "Username must be at least 3 characters."
    if uname in users:
        return False, f"Username '{uname}' already exists."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    pwd_hash, salt = _hash_password(password)
    users[uname] = {
        "username": uname,
        "password_hash": pwd_hash,
        "salt": salt,
        "role": "user",
        "status": "pending",
        "note": note.strip() or "Standard member request",
        "created_at": datetime.utcnow().isoformat(),
        "last_login": None,
    }
    _save_users(users)
    return True, "Access request submitted successfully! An Admin must approve your account before you can log in."


def list_users() -> List[dict]:
    """Return all registered users (excluding sensitive password hash and salt)."""
    users = _load_users()
    clean_list = []
    for u in users.values():
        clean_list.append({
            "username": u.get("username"),
            "role": u.get("role", "user"),
            "status": u.get("status", "pending"),
            "note": u.get("note", ""),
            "created_at": u.get("created_at", "")[:19].replace("T", " "),
            "last_login": (u.get("last_login") or "Never")[:19].replace("T", " "),
        })
    return clean_list


def approve_user(username: str) -> bool:
    """Approve a pending user."""
    users = _load_users()
    uname = username.strip().lower()
    if uname in users:
        users[uname]["status"] = "approved"
        _save_users(users)
        return True
    return False


def reject_user(username: str) -> bool:
    """Reject or revoke access for a user."""
    users = _load_users()
    uname = username.strip().lower()
    if uname in users and users[uname].get("role") != "admin":
        users[uname]["status"] = "rejected"
        _save_users(users)
        return True
    return False


def delete_user(username: str) -> bool:
    """Delete a user account (cannot delete admin)."""
    users = _load_users()
    uname = username.strip().lower()
    if uname in users and users[uname].get("role") != "admin":
        del users[uname]
        _save_users(users)
        return True
    return False


def add_user_direct(username: str, password: str, role: str = "user", note: str = "") -> Tuple[bool, str]:
    """Admin-only: directly add a pre-approved user or admin."""
    users = _load_users()
    uname = username.strip().lower()
    if not uname or len(uname) < 3:
        return False, "Username must be at least 3 characters."
    if uname in users:
        return False, f"Username '{uname}' already exists."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    pwd_hash, salt = _hash_password(password)
    users[uname] = {
        "username": uname,
        "password_hash": pwd_hash,
        "salt": salt,
        "role": role if role in ["admin", "user"] else "user",
        "status": "approved",
        "note": note.strip() or "Created by Administrator",
        "created_at": datetime.utcnow().isoformat(),
        "last_login": None,
    }
    _save_users(users)
    return True, f"User '{uname}' added and approved."


def change_password(username: str, new_password: str) -> Tuple[bool, str]:
    """Change a user's password."""
    users = _load_users()
    uname = username.strip().lower()
    if uname not in users:
        return False, "User not found."
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters."
    pwd_hash, salt = _hash_password(new_password)
    users[uname]["password_hash"] = pwd_hash
    users[uname]["salt"] = salt
    _save_users(users)
    return True, "Password updated successfully."
