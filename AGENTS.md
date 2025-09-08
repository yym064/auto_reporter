# Repository Guidelines

## Project Structure & Module Organization
- Root: project configuration and this guide.
- `src/`: application code (organize by feature, not layer).
- `tests/`: automated tests mirroring `src/` structure.
- `scripts/`: repeatable dev ops (setup, build, release).
- `assets/` or `public/`: static files and sample data.
- `docs/`: architecture notes and ADRs.

Example:
```
report_project/
  src/
    feature_a/
  tests/
    feature_a/
  scripts/
  docs/
```

## Build, Test, and Development Commands
Prefer using a Makefile (or equivalent) as a thin wrapper so commands stay consistent:
- `make setup`: install dependencies and pre-commit hooks.
- `make dev`: run the app locally with reload if supported.
- `make test`: run the test suite with coverage.
- `make lint`: run static checks and formatters.
- `make build`: produce a production build or artifact.

If a Makefile is not present, use language defaults, e.g.:
- Node: `npm ci`, `npm run dev`, `npm test`, `npm run lint`, `npm run build`
- Python: `uv sync` or `pip install -r requirements.txt`, `pytest -q`, `ruff check`, `black .`

## Coding Style & Naming Conventions
- Structure by feature: `src/<feature>/[api|service|model].*`.
- Names: snake_case for files in Python, kebab-case for JS/TS files and folders, PascalCase for classes, camelCase for functions/variables.
- Formatting: use auto-formatters; do not hand-format diffs.
- Linting: enable strict rules; fix or justify suppressions inline.

## Testing Guidelines
- Frameworks: prefer `pytest` (Python) or `vitest/jest` (JS/TS).
- Location: `tests/<feature>/` matching `src/<feature>/`.
- Naming: `test_<unit>.py` or `<unit>.test.ts`.
- Coverage: target ≥90% for changed lines; add regression tests for bugs.
- Run locally: `make test` and include failing test first when fixing issues.

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits, e.g. `feat: add report exporter` or `fix(report): correct date parsing`.
- Scope: small, focused commits with clear messages.
- PRs: include description, motivation, before/after notes, screenshots or logs if UI/CLI, and linked issues. Request review early with a checklist of risks.

## Security & Configuration Tips
- Keep secrets in environment files not committed (`.env`, `.env.local`).
- Add example config: `cp .env.example .env`.
- Validate inputs and sanitize any file or network operations.
