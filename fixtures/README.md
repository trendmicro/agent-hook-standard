# Fixtures

Fixtures prove the expected behavior of schemas accepted by the Agent Hook
Spec. There are no fixtures until the first schema is adopted.

For `schemas/<name>.schema.json`, create JSON payloads in:

```text
fixtures/<name>/valid/
fixtures/<name>/invalid/
```

The validation script requires valid fixtures to pass and invalid fixtures to
fail. Use focused fixture names that describe the scenario.
