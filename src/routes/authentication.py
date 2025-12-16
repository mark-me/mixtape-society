from flask import session, redirect, Blueprint, Response, request, flash, current_app




def create_authentication_blueprint(logger, limiter) -> Blueprint:
    """
    Creates and returns a Flask blueprint for user authentication routes.

    Sets up login and logout endpoints for handling user authentication and session management.

    Returns:
        Blueprint: The Flask blueprint with authentication routes.
    """
    authenticator = Blueprint("authenticator", __name__)



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
