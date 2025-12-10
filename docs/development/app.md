# App

The file `app.py` defines the main Flask application for the "mixtape-society" project. It is responsible for initializing the web server, configuring the application based on the environment, setting up core services (such as music collection management), and registering routes and blueprints for handling various web requests. The file serves as the entry point for the application, orchestrating authentication, static file serving, and integration with modular route handlers.

## Key Components

* **Environment Configuration**

    The application selects its configuration (development, test, or production) based on the APP_ENV environment variable. It loads the appropriate config class and ensures necessary directories exist.

* **Flask App Initialization**

    The Flask app is created and configured with a secret key for session management. The app also sets up custom MIME types for various audio formats.

* **Core Services**
  ** `MusicCollection`: Manages the music library, initialized with paths from the configuration.
  ** `MixtapeManager`: Used for retrieving mixtape data, especially for public sharing.
* **Authentication Routes**
  * `/login`: Handles user login by checking a password and setting a session variable.
  * `/logout`: Logs out the user by clearing the session.
* **Static File Serving**
  * `/mixtapes/files/<path:filename>`: Serves mixtape files from a configured directory.
  * `/covers/<filename>`: Serves cover images from a configured directory.
* **Public Mixtape Sharing**
  * `/share/<slug>`: Renders a public playback page for a mixtape identified by a slug. If the mixtape does not exist, a 404 error is returned.
* **Template Context Injection**
  * `inject_now`: Adds the current UTC datetime to the template context, making it available as now in templates.
* **Blueprint Registration**

    The app registers three blueprints (`browser`, `play`, `editor`) to modularize route handling and keep the main file organized.

* **App Runner**

    serve() function and the if __name__ == "__main__" block both start the Flask development server on all interfaces at port 5000.

## API

### ::: src.app
