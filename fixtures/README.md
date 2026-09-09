# Fixtures

Fixtures prove the expected behavior of Agent Hook schemas. The 0.1 draft
includes fixtures for `hook-event` and `hook-response`.

For `schemas/<name>.schema.json`, create JSON payloads in:

```text
fixtures/<name>/valid/
fixtures/<name>/invalid/
```

The validation script requires valid fixtures to pass and invalid fixtures to
fail. Use focused fixture names that describe the scenario.
