---
sidebar_position: 4
---

# Conformance

Agent Hook 0.1 defines three conformance roles: event producer, handler, and
adapter. The draft's normative requirements and role definitions are in the
[core protocol](https://trendmicro.github.io/agent-hook-standard/specification/0.1/core).

The repository validates the 0.1 event and response JSON Schemas against
focused valid and invalid fixtures. Each schema uses JSON Schema Draft 2020-12,
declares a stable identifier and title, and is published at its versioned schema
URL. Run the following checks before requesting review:

```sh
npm run validate
npm run build
```

Schema validation proves document shape, not complete runtime behavior. An
adapter review must additionally verify correct event mapping, `event_id`
correlation, decision handling, and the required fail-open behavior for invalid,
missing, timed-out, or errored handler responses.
