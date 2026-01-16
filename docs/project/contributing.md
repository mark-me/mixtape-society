![Contributing](../images/contributing.png){ align=right width="90" }

# Contributing

Interested in helping out? Here's how things work.

## 🤝 Ways to Contribute

**Share ideas** - Open a [discussion](https://github.com/mark-me/mixtape-society/discussions) or comment on existing ones. All suggestions welcome, even half-baked ones.

**Report bugs** - [Open an issue](https://github.com/mark-me/mixtape-society/issues) with:
- What you expected to happen
- What actually happened
- Steps to reproduce (if possible)
- Your setup (Docker/local, browser, OS)

**Improve documentation** - Typos, unclear explanations, missing info—all fair game. Docs live in the `/docs` folder.

**Code contributions** - Check [good first issue](https://github.com/mark-me/mixtape-society/labels/good%20first%20issue) tags or the [roadmap](roadmap.md) for things I'm planning to work on.

## 🧭 Before You Start

If you're thinking of tackling something substantial (new feature, big refactor), open an issue or discussion first. Saves everyone time if the direction doesn't fit the project.

## 🛠️ Development Setup

### Using Docker (Recommended)

See [Docker Development guide](../development/docker-dev.md) for full instructions.

### Local Development

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society
uv sync  --group dev

# Edit MUSIC_ROOT and APP_PASSWORD in .env
uv run python app.py
```

First run will index your music library.

See [Local Development guide](../development/docker-dev.md) for more details.

## 🎨 Code Style

Nothing strict, but:
- Keep it readable
- Add docstrings for non-obvious functions
- Follow existing patterns in the codebase
- Run basic tests if you're changing core functionality

If something's unclear, just ask.

## 🔀 Pull Request Process

1. Fork the repo
2. Create a branch (`git checkout -b feature/thing`)
3. Make your changes
4. Commit with a clear message
5. Push and open a PR

I'll review when I can. Might ask for changes, might take a while—this is a side project.

## 🗂️ Project Organization

The [GitHub Project board](https://github.com/mark-me/mixtape-society/projects) tracks work in progress:

- **Ideas** - Things being explored ([Ideas doc](ideas/ideas.md) has more)
- **Planned** - Committed to building ([Roadmap](roadmap.md))
- **In Progress** - Currently working on
- **Done** - Shipped (see [Changelog](changelog.md))

It's pretty informal, just helps keep things organized.

## 🎯 What Gets Prioritized

Roughly in this order:

1. Bug fixes (especially breaking ones)
2. Features that align with project goals (see [About](about.md))
3. Community interest (reactions, comments on issues)
4. Maintainer availability (aka: when I have time)

## 🧪 Testing

Basic manual testing is fine for most changes. If you're modifying core components (musiclib, audio caching, database), please test thoroughly:

- Try it with your own music library
- Test edge cases (empty folders, weird filenames, large libraries)
- Check it doesn't break existing features

No formal test suite yet, but that might change.

## 📚 Documentation

If your PR adds a feature or changes behavior:
- Update relevant docs in `/docs`
- Add a brief note in `CHANGELOG.md` (I'll handle version numbering)

## ❓ Questions?

Not sure about something? Open a [discussion](https://github.com/mark-me/mixtape-society/discussions) or comment on a relevant issue. I'll respond when I can.

## ⚖️ License

By contributing, you agree your contributions will be licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

Thanks for considering contributing to Mixtape Society. Even small fixes are appreciated. 🎧
