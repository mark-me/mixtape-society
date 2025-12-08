from flask import session, redirect, url_for

def check_auth():
    return session.get("authenticated")

def require_auth(view):
    from functools import wraps
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not check_auth():
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapper