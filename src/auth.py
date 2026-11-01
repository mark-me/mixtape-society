import hashlib
import hmac
import os
import secrets
import tempfile
from pathlib import Path
from typing import Callable

from flask import session, redirect, url_for


def derive_session_key(data_root: Path, password: str) -> str:
    """
    Derives the key that signs session cookies.

    Combines a random key kept in the data directory with the password. A session
    cookie therefore says nothing about the password, and changing the password
    still logs everyone out.

    Args:
        data_root: Directory that holds the random key file.
        password: The configured login password.

    Returns:
        str: The key to use as the Flask secret key.
    """
    random_key = _load_or_create_key(Path(data_root) / "session_key")
    return hmac.new(random_key, password.encode(), hashlib.sha256).hexdigest()


def _load_or_create_key(path: Path) -> bytes:
    """
    Reads the random key file, creating it on first use.

    The file is written under a temporary name and then linked into place, so
    several workers starting together all end up with the same complete key.

    Args:
        path: Location of the key file.

    Returns:
        bytes: The key.
    """
    if not path.exists():
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete_on_close=False) as tmp:
            tmp.write(secrets.token_hex(32))
            tmp.close()
            try:
                os.link(tmp.name, path)
            except FileExistsError:
                pass
    return path.read_bytes()


def password_matches(submitted: str | None, configured: str | None) -> bool:
    """
    Compares a submitted password with the configured one in constant time.

    Args:
        submitted: The password from the login form, if any.
        configured: The configured password, if any.

    Returns:
        bool: True only if both are present and equal.
    """
    if not submitted or not configured:
        return False
    return hmac.compare_digest(submitted.encode(), configured.encode())


def check_auth() -> bool:
    """
    Checks if the current user is authenticated.

    Returns True if the user is authenticated in the session, otherwise False.

    Returns:
        bool: Authentication status of the current user. Returns True only if the
        session "authenticated" flag is explicitly set to True.
    """
    return session.get("authenticated") is True

def require_auth(view: Callable) -> Callable:
    """
    Decorator that enforces authentication for a view function.

    Redirects unauthenticated users to the landing page before allowing access to the decorated view.

    Args:
        view: The view function to be protected.

    Returns:
        function: The wrapped view function with authentication enforcement.
    """
    from functools import wraps
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not check_auth():
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapper