<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# docs

## Purpose
Reference documentation for the current local-only proxy: API contract, architecture, usage, implementation status, historical evidence, and migration notes. This directory explains both the supported surface area and the reasoning/history behind decisions such as removing cloud backend support.

## Key Files

| File | Description |
|------|-------------|
| `API_CONTRACT.md` | Canonical request/response/error contract, supported compatibility fields, model exposure rules, and environment variables |
| `ARCHITECTURE.md` | Local-only runtime architecture, request lifecycle, version probing, model discovery, conversation continuation, and streaming flow |
| `IMPLEMENTATION_STATUS.md` | Current feature status plus the verification commands that have been run successfully |
| `USAGE.md` | Quick start, curl examples, and Open WebUI / Continue connection instructions |
| `CLIPROXYAPI.md` | Integration guide for wiring warptocli into CLIProxyAPI-style OpenAI-compatible setups |
| `DECISIONS.md` | ADR log and design rationale, including historical choices that may predate later simplifications |
| `EVIDENCE.md` | Research basis, CLI observations, and validation evidence, including historical cloud investigation records |
| `CLOUD_REMOVED.md` | Explicit note describing what cloud support was removed and where to recover it from git history if ever needed |

## Subdirectories
This directory currently has no child directories that require separate `AGENTS.md` files.

## For AI Agents

### Working In This Directory
- Treat `API_CONTRACT.md` as the source of truth for the supported HTTP surface
- Treat `IMPLEMENTATION_STATUS.md` and `CLOUD_REMOVED.md` as the current implementation reality when older docs disagree
- Read `DECISIONS.md` and `EVIDENCE.md` as rationale/history documents; some sections intentionally preserve pre-removal cloud context
- When behavior changes, update the matching contract, status, and usage docs together rather than patching just one file
- Do not place runnable application code in this directory

### Testing Requirements
- Documentation-only edits usually do not need separate tests, but any documented command or API example should remain consistent with the implementation
- When API behavior changes, run `pytest -q` and refresh the affected examples or verification notes

### Common Patterns
- Most files start with metadata bullets such as last-updated date and status/scope
- Contract and usage docs prefer concise tables, curl examples, and cross-links to related documents
- Historical or superseded behavior is called out explicitly instead of being silently deleted when it is still useful context

## Dependencies

### Internal
- Documents describe `main.py`, `config.py`, `models.py`, `oz_bridge.py`, `conversation_store.py`, and the `tests/` suite
- `IMPLEMENTATION_STATUS.md` and `EVIDENCE.md` reference commands and fixtures from `tests/fixtures/oz/`

### External
- Oz CLI / Warp session behavior is the external system being documented
- FastAPI and OpenAI-compatible client behavior shape the public contract described here

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

