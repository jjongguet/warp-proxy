<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# fixtures/oz

## Purpose
Sanitized captures of Oz CLI output used for deterministic parser and response-shape verification. The active local-only implementation depends on the local NDJSON and version fixtures, while the cloud-related captures are preserved as historical evidence for documentation and potential future recovery work.

## Key Files

| File | Description |
|------|-------------|
| `README.md` | Short provenance note explaining what the fixture set contains and why it exists |
| `dump_debug_info_supported.txt` | Verified `oz dump-debug-info` output containing the supported Warp CLI version line |
| `live_local_success.ndjson` | Minimal successful local `oz agent run --output-format json` capture with a redacted conversation ID |
| `live_stream_events.ndjson` | Local NDJSON event sequence used to validate streaming-event parsing |
| `live_stream_sse.txt` | Example proxy SSE framing for a successful streamed completion |
| `live_cloud_launch_summary.txt` | Historical `oz agent run-cloud` launch summary kept for evidence and migration notes |
| `live_cloud_run_get_success.txt` | Historical `oz run get` success output kept as a reference for removed cloud support |
| `live_cloud_success_summary.txt` | Historical ambient cloud summary capture retained alongside the other removed-cloud artifacts |

## Subdirectories
This directory currently has no child directories that require separate `AGENTS.md` files.

## For AI Agents

### Working In This Directory
- Do not edit fixtures just to make tests pass; fix the parser or refresh the capture from real CLI behavior when assumptions change
- Preserve sanitization/redaction when replacing live captures
- Keep historical cloud fixtures unless there is a deliberate cleanup or feature-revival decision tied to the docs
- Add a short README note or AGENTS update when introducing a new fixture family

### Common Patterns
- `.ndjson` files contain one JSON event per line from `oz agent run --output-format json`
- `.txt` files capture plain-text CLI summaries or expected SSE output
- Local fixtures should track the currently supported CLI contract; cloud fixtures are explicitly historical in this codebase

## Dependencies

### Internal
- `tests/test_oz_bridge.py` and `tests/test_api.py` read these fixtures through `pathlib.Path`
- `docs/EVIDENCE.md` and `docs/CLOUD_REMOVED.md` reference the historical cloud captures

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

