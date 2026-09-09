# Schemas

This directory contains machine-readable JSON Schemas for Agent Hook Spec
versions. The 0.1 draft defines `hook-event.schema.json` and
`hook-response.schema.json`. Each schema declares JSON Schema Draft 2020-12,
a stable `$id`, and a descriptive `title`.

Place a schema at `schemas/<name>.schema.json`. Pair it with fixtures at
`fixtures/<name>/valid/` and `fixtures/<name>/invalid/`. Valid fixtures must
validate; invalid fixtures must fail validation. Add normative explanation in
`spec/` and illustrative integrations in `examples/` alongside schema changes.
