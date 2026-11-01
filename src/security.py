from urllib.parse import urlsplit

from flask import Flask, abort, request

# What a page may load, besides itself. Only reported for now, in the browser's console: the
# templates still use inline scripts, which an enforced policy would stop.
_REPORTED_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://www.gstatic.com",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

# Cross-Origin-Opener-Policy stays out: it can cut off the window the Cast SDK talks to.
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

# Methods that change nothing; any other must come from a page of the app itself.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def register_security(app: Flask) -> None:
    """
    Adds the security checks and headers to every request of the app.

    Args:
        app: The Flask application.
    """
    app.before_request(reject_other_sites)
    app.after_request(add_security_headers)


def reject_other_sites() -> None:
    """
    Refuses a change that comes from another site, so a visitor can't be tricked into sending it.

    Browsers say where a request comes from. Sec-Fetch-Site must then be same-origin; a browser
    that doesn't send it, as over plain HTTP, still sends Origin, which must be this host. A
    request with neither is not a browser's.
    """
    if request.method in _SAFE_METHODS:
        return
    site = request.headers.get("Sec-Fetch-Site")
    if site is not None:
        if site not in ("same-origin", "none"):
            abort(403)
        return
    origin = request.headers.get("Origin")
    if origin is not None and (origin == "null" or urlsplit(origin).netloc != request.host):
        abort(403)


def add_security_headers(response):
    """
    Adds the security headers to a response.

    The help is left out of the reported policy: it is the documentation site, whose theme
    runs inline scripts of its own and holds nothing but our own pages.

    Args:
        response: The response.

    Returns:
        Response: The same response, with the headers added.
    """
    for name, value in _HEADERS.items():
        response.headers.setdefault(name, value)
    if request.blueprint != "help":
        response.headers["Content-Security-Policy-Report-Only"] = _REPORTED_POLICY
    return response
