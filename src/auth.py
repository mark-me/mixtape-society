from flask import session, redirect, url_for

def check_auth():
    """
    Checks if the current user is authenticated.

    Returns True if the user is authenticated in the session, otherwise False.

    Returns:
        bool: Authentication status of the current user.
    """
    return session.get("authenticated")

def require_auth(view):
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