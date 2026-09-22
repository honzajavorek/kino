# Guidance for AI agents

## Design

- Keep changes small and code straightforward. Prefer explicit steps over a generic framework or abstractions used only once.
- Keep crawling, caching, and file writing at the edges; put HTML parsing, screening decisions, and calendar data preparation in small, typed functions.
- Use Python type hints, keep branching shallow, and arrange functions from entry points to smaller helpers where practical.
- Follow the project's existing async code and tools: `uv`, `click`, Crawlee, and Ruff. Keep imports at module level and avoid `TYPE_CHECKING` blocks.
- Preserve cinema selection, Prague time zone handling, film and Aero pairing, event contents, and output files. The Camoufox/CSFD challenge handling has deliberate waits, retries, and session settings; read its comments before simplifying it.
- Keep logs useful without exposing credentials or other secrets.

## Tests and verification

- For behavior changes, work red-green: write a failing focused test first, then make it pass.
- Favor fast tests of pure parsers and transformations, with fewer tests around crawler and file boundaries. Keep default tests independent of network and current time. Save representative remote HTML as fixtures and add edge-case fixtures when needed.
- Use parametrized tests for related cases; give tests descriptive names and focused assertions.
- Run `uv run pytest` after Python changes; this project's pytest configuration also runs Ruff lint and format checks.
