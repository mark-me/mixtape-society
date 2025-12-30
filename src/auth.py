from flask import session, redirect, url_for
from typing import Callable

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