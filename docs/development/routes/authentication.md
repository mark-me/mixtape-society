![Authentication](../../images/authentication.png){ align=right width="90" }

# Authentication

The `routes/authentication.py` file defines the authentication subsystem for the Flask app as a reusable blueprint. it's purpose is to centralize login/logout behavior, enforce rate limiting on login attempts, and provide a blueprint that can be registered on the main Flask app to enable password-based access control using a single shared secret.

Functionally, it:

- Creates an authentication blueprint
    - `create_authentication_blueprint(limiter, logger=None)` constructs and returns a Blueprint named "authenticator".
    - It accepts:
        - A `Limiter` instance (from `flask_limiter`) used to rate-limit login attempts.
        - An optional `Logger` for recording authentication-related events (with a `NullLogger` fallback, though the current code doesn’t explicitly log yet).
- Implements login logic (`POST /login`)
    - Exposed as `/login` on the authentication blueprint.
    - Protected by `@limiter.limit("5 per minute")`, meaning each client can only attempt login five times per minute.
    - Reads the `password` field from `request.form`.
    - Compares the submitted password to `current_app.secret_key`:
        - If they match: sets `session["authenticated"] = True`.
        - If they do not match: uses `flash("Invalid password", "danger")` to send an error message to the UI.
    - Always redirects to `/` afterward (both success and failure).
- Implements logout logic (`GET /logout`)
    - Exposed as `/logout` on the `authentication` blueprint.
    - Removes the authenticated flag from the session (`session.pop("authenticated", None)`).
    - Redirects the user back to `/` (the landing or main page).

## API

### ::: src.routes.authentication
