For additional context about technologies to be used, project structure,
shell commands, and important constraints, read the current plan at
`specs/001-science-mvp/plan.md` and the governing constitution at
`.specify/memory/constitution.md`.

## Quick orientation

- **Audience**: researcher only (per Constitution §IV).
- **Stack**: stdlib Python ≥ 3.9 (per Constitution §X).
- **Slash commands**: exactly five — `research`, `ask`, `discover`,
  `verify`, `rigor`. Adding a sixth requires a constitution amendment.
- **CLI entry point**: `python3 -m cannavec_science <subcommand>`.
- **Tests**: `python3 -m unittest discover -s tests` runs offline.
