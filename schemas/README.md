# Schemas

This directory contains machine-readable JSON Schemas for Agent Hook Spec
versions. The 0.1 draft defines `hook-event.schema.json` and
`hook-response.schema.json`. Each schema declares JSON Schema Draft 2020-12,
a stable `$id`, and a descriptive `title`.

The published 0.1 downloads use the `agent-hook-unity` website; see the
[core protocol](../spec/0.1/core.md) for download links. The schemas retain
their original 0.1 `$id` values for compatibility. These identifiers are
independent of the download URLs.

Place a schema at `schemas/<name>.schema.json`. Pair it with fixtures at
`fixtures/<name>/valid/` and `fixtures/<name>/invalid/`. Valid fixtures must
validate; invalid fixtures must fail validation. Add normative explanation in
`spec/` and illustrative integrations in `examples/` alongside schema changes.
