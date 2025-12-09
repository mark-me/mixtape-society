# Mixtape Society Application Documentation

## Overview

Mixtape Society is a web application for creating, managing, and sharing music mixtapes. It provides user authentication, audio streaming, mixtape management, and cover image serving, all built on the Flask web framework.

## Main Features

- **User Authentication:** Secure login and logout functionality using session-based authentication.
- **Audio Streaming:** Stream audio files from the music collection with support for HTTP range requests (seeking).
- **Mixtape Management:** Create, save, list, and share mixtapes, including cover image processing and metadata management.
- **Cover Image Serving:** Serve cover images for mixtapes from a dedicated directory.
- **Public Sharing:** Share mixtapes via public URLs for playback without authentication.

## Application Structure

- **Configuration:** Uses environment-based configuration classes (`DevelopmentConfig`, `TestConfig`, `ProductionConfig`) to set paths, passwords, and debug settings.
- **Blueprints:** Modularizes routes into blueprints for browsing, editing, and playing mixtapes.
- **Routes:**
  - `/` - Landing page
  - `/login` - User login
  - `/logout` - User logout
  - `/play/<path:file_path>` - Stream audio files
  - `/mixtapes/files/<path:filename>` - Serve mixtape files
  - `/covers/<filename>` - Serve cover images
  - `/share/<slug>` - Public mixtape playback

## Key Components

- **MusicCollection:** Handles searching and highlighting tracks in the music library.
- **MixtapeManager:** Manages saving, listing, and retrieving mixtapes and their cover images.
- **Authentication:** Decorators and session management for user authentication.
- **Audio Streaming:** Validates file paths, determines MIME types, and supports partial content delivery for audio files.

## Template Context

- Injects the current UTC datetime into templates for dynamic display of time.

## Running the Application

To start the application, run:

```bash
python [src/app.py](VALID_FILE)


if __name__ == "__main__":
    app.run(debug=True)
