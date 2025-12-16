from flask import session, redirect, Blueprint, Response, request, flash, current_app

from flask_limiter import Limiter

from common.logging import Logger, NullLogger

def create_authentication_blueprint(limiter: Limiter, logger: Logger | None = None) -> Blueprint:
    """
    Creates and configures the Flask blueprint for user authentication.

    Sets up routes for user login and logout, applies rate limiting to login attempts, and provides logging support.

    Args:
        limiter (Limiter): The Flask-Limiter instance for rate limiting login attempts.
        logger (Logger | None): Optional logger for logging authentication events. Uses NullLogger if not provided.

    Returns:
        Blueprint: The configured Flask blueprint for authentication.
    """

    authenticator = Blueprint("authenticator", __name__)

    logger: Logger = logger or NullLogger()

    # === Authentication Routes ===
    @authenticator.route("/login", methods=["POST"])
    @limiter.limit("5 per minute")
    def login() -> Response:
        """
        Authenticates a user based on the submitted password.

        Checks the provided password against the configured password and sets the session as authenticated if correct.
        Redirects to the mixtapes page on success or flashes an error and redirects to the landing page on failure.

        Returns:
            Response: The Flask response object for the appropriate redirect.
        """
        password = request.form.get("password")
        if password == current_app.secret_key:
            session["authenticated"] = True
        else:
            flash("Invalid password", "danger")
        return redirect("/")

    @authenticator.route("/logout")
    def logout() -> Response:
        """
        Logs out the current user by removing authentication from the session.

        Clears the user's session and redirects to the landing page.

        Returns:
            Response: The Flask response object for the redirect to the landing page.
        """
        session.pop("authenticated", None)
        return redirect("/")

    return authenticator
