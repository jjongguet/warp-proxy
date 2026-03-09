# docs/

This directory contains all reference documentation for warp-proxy.
Start here to find the right document for your question.

---

## Document Authority Chain

When documents conflict, this precedence order applies:

| Priority | Document | Scope |
|----------|----------|-------|
| 1 | [`API_CONTRACT.md`](./API_CONTRACT.md) | HTTP contract — canonical source of truth for all API behavior |
| 2 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System design and component boundaries |
| 3 | [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) | Feature matrix and verification evidence |
| — | All others | Supplementary — defer to the above when in conflict |

---

## Where to Start

**I want to use the proxy →** [`USAGE.md`](./USAGE.md)

**I want to integrate with CLIProxyAPI →** [`CLIPROXYAPI.md`](./CLIPROXYAPI.md)

**I want to understand the API surface →** [`API_CONTRACT.md`](./API_CONTRACT.md)

**I want to understand the system design →** [`ARCHITECTURE.md`](./ARCHITECTURE.md)

**I want to know what is implemented →** [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md)

**I want to understand past decisions →** [`DECISIONS.md`](./DECISIONS.md)

**I am an AI agent →** See the [For AI Agents](#for-ai-agents) section below.

---

## Active Documentation

| File | Purpose |
|------|---------|
| [`API_CONTRACT.md`](./API_CONTRACT.md) | Canonical HTTP contract — endpoints, request/response shapes, error codes, model IDs |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Runtime architecture, request lifecycle, streaming flow, version probing |
| [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) | Implemented feature matrix and verification snapshot |
| [`USAGE.md`](./USAGE.md) | Quick start, curl examples, client integration (Claude Code, Codex CLI, Open WebUI, Continue) |
| [`CLIPROXYAPI.md`](./CLIPROXYAPI.md) | CLIProxyAPI integration guide (OpenAI-compatible and Anthropic-compatible modes) |
| [`DECISIONS.md`](./DECISIONS.md) | Architecture decision records (ADRs) — rationale behind key choices |

---

## Historical / Reference

These documents are retained for context. They describe past decisions or superseded designs.
For current behavior, refer to the Active Documentation above.

| File | Purpose |
|------|---------|
| [`EVIDENCE.md`](./EVIDENCE.md) | Design rationale, CLI observations, and validation records (including cloud investigation) |
| [`CLOUD_REMOVED.md`](./CLOUD_REMOVED.md) | Why cloud backend support was removed on 2026-03-09 |
| [`archive/PRD.md`](./archive/PRD.md) | Original product requirements draft — historical planning artifact |

---

## For AI Agents

- **Source of truth for API behavior:** `API_CONTRACT.md`
- **Source of truth for what is implemented:** `IMPLEMENTATION_STATUS.md`
- **Do not** use `EVIDENCE.md`, `CLOUD_REMOVED.md`, or `archive/PRD.md` as current contracts
- **Do not** reintroduce cloud backend support without updating docs, tests, and compatibility notes together
- When behavior changes, update `API_CONTRACT.md`, `IMPLEMENTATION_STATUS.md`, and `USAGE.md` together
- See root `AGENTS.md` for codebase-wide conventions and `docs/AGENTS.md` for docs-directory conventions
