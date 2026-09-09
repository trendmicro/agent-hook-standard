# Schemas

This directory will contain the machine-readable JSON Schemas for accepted
Agent Hook Spec versions. Each schema must declare JSON Schema Draft 2020-12,
a stable `$id`, and a descriptive `title`.

Place a schema at `schemas/<name>.schema.json`. Pair it with fixtures at
`fixtures/<name>/valid/` and `fixtures/<name>/invalid/`. Valid fixtures must
validate; invalid fixtures must fail validation. Add normative explanation in
`spec/` and illustrative integrations in `examples/` alongside schema changes.
