# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a clean workspace with no source files or build configuration. As the project is added, keep application code in a clearly named source directory (for example, `src/`), tests in `tests/` or alongside modules using the project’s standard convention, and static resources in `assets/` or `public/`. Group related functionality by feature rather than creating a large miscellaneous utilities directory. Update this guide when the final framework and directory layout are established.

## Build, Test, and Development Commands

No build, test, or development scripts are configured yet. Once tooling is selected, document the canonical commands here and keep them reproducible from the repository root. Typical entries might include:

- `npm install` — install dependencies.
- `npm run dev` — start the local development server.
- `npm run build` — create a production build.
- `npm test` — run the automated test suite.

Prefer repository scripts over one-off global commands, and record any required environment variables in an example configuration file.

## Coding Style & Naming Conventions

Follow the formatter and linter adopted by the project, and run them before opening a pull request. Use consistent two- or four-space indentation according to the language tooling; do not mix styles within a file. Use descriptive names: `PascalCase` for types/components, `camelCase` for functions and variables, and `kebab-case` for directories or URL-oriented files unless the framework requires otherwise.

## Testing Guidelines

Add tests for new behavior and regressions. Name test files consistently with the implementation (for example, `bar-service.test.ts`) and keep tests deterministic, isolated, and readable. Document the selected test framework and any coverage threshold here once configured.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects such as `Add route planner` or `Fix venue filtering`. Keep commits focused and explain meaningful behavior or migration details in the body. Pull requests should include a concise summary, testing performed, relevant issue links, configuration or schema changes, and screenshots or recordings for user-facing changes.

## Security & Configuration Tips

Never commit credentials, API keys, or private data. Add local secrets to an ignored `.env` file and provide safe placeholders in `.env.example`. Validate external input and review dependency or configuration changes before merging.
