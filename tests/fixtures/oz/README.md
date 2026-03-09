# Oz fixtures

These fixtures are sanitized captures used to validate the current NDJSON-backed Oz adapter.

## Files
- `live_local_success.ndjson`
  - Captured from a real local `oz agent run --output-format json` success on 2026-03-08
  - `conversation_id` was redacted/replaced
- `dump_debug_info_supported.txt`
  - Minimal captured version probe output containing the verified Warp CLI version line

## Purpose
These fixtures help pin the current parser assumptions without requiring live Oz access for every test run.
