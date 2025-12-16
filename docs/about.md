# About Mixtape Society

![Mixtape Society Logo](images/cassette-fill-white.svg){ align=right width="150" }

Mixtape Society is a self-hosted web application that lets you create, manage, and share personalized music mixtapes from your own music library. Inspired by the nostalgia of cassette tapes, it brings a modern twist: drag-and-drop editing, custom covers, and public share links for easy listening without accounts or apps.

## Project Goals

- **Privacy-First**: Everything runs on your hardware—no cloud uploads, no tracking.
- **Simplicity**: Easy to set up and use, even for non-techies.
- **Nostalgia Meets Modern**: Recreate the joy of mixtapes with features like themes and browser-based streaming.
- **Open Source**: Free and open for contributions, under the [MIT License](https://mit-license.org/).

## Who Built This?

Hi, I'm Mark Zwart (e.g., mark-me on GitHub), a I'm a Dutch developer and music enthusiast based in The Netherlands. I created Mixtape Society because I wanted a simple way to share curated playlists from my personal collection without relying on big streaming services.

If you'd like to connect:

- GitHub: [github.com/mark-me](https://github.com/mark-me)

## Acknowledgements

Mixtape Society leverages several fantastic open-source libraries and tools. A big thank you to the developers and communities behind these projects.

### Python & Backend

- **[Flask](https://flask.palletsprojects.com/)** – The lightweight and elegant web framework that powers everything
- **[Jinja2](https://jinja.palletsprojects.com/)** – The powerful templating engine used for dynamic HTML rendering in all pages.
- **[Flask-CORS](https://flask-cors.readthedocs.io/)** – Simple cross-origin resource sharing
- **[Flask-Limiter](https://flask-limiter.readthedocs.io/)** – Rate limiting for the login route
- **[Flask-Login](https://flask-login.readthedocs.io/)** – Session management
- **[Gunicorn](https://gunicorn.org/)** – Production WSGI server
- **[Pillow](https://python-pillow.org/)** – Image processing for uploaded covers
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** – Easy .env file support
- **[python-json-logger](https://github.com/madzak/python-json-logger)** – Structured logging
- **[TinyTag](https://github.com/devsnd/tinytag)** – Fast and lightweight audio metadata reading
- **[Watchdog](https://github.com/gorakhargosh/watchdog)** – File system events for auto-reindexing the music library
- **[SQLite](https://www.sqlite.org/)** – Embedded, zero-configuration database that stores your entire music library index and makes instant search possible.

### Documentation

- **[MkDocs](https://www.mkdocs.org/)** & **[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)** – Static documentation you’re reading right now
- **[mkdocstrings](https://mkdocstrings.github.io/)** – Auto-generated API docs from code
- **[mkdocs-git-revision-date-localized-plugin](https://github.com/timvink/mkdocs-git-revision-date-localized-plugin)** – Page last-updated dates
- **[mkdocs-git-committers-plugin](https://github.com/byrnereese/mkdocs-git-committers-plugin)** – Contributor credits
- **[mkdocs-panzoom-plugin](https://github.com/lucasmaystre/mkdocs-panzoom)** – Zoomable screenshots
- **[mermaid2](https://github.com/Franiac/mkdocs-mermaid2-plugin)** – Diagrams

### Frontend & Design

- **[Bootstrap 5](https://getbootstrap.com/)** – The entire responsive UI, cards, buttons, modals, and grid system
- **[Bootstrap Icons](https://icons.getbootstrap.com/)** – All the lovely icons you see everywhere
- **[Sortable.js](https://sortablejs.github.io/Sortable/)** – Drag-and-drop reordering in the editor
- **[Placeholder.com](https://placeholder.com/)** – Simple placeholder images for default covers

## License

Mixtape Society is released under the [MIT License](https://mit-license.org/). Feel free to fork, modify, and share—but remember, users are responsible for their own music content (no copyrighted media is included or distributed).

## Get Involved

- Report issues or suggest features on [GitHub Issues](https://github.com/mark-me/mixtape-society/issues).
- Star the repo if you like it!

Thanks for checking out Mixtape Society—happy mixtaping! 🎧
