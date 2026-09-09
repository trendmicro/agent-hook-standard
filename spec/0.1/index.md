---
sidebar_position: 1
slug: /0.1
---

# Agent Hook 0.1 draft

Agent Hook 0.1 is a draft portable security and telemetry contract for an agent
runtime to deliver a lifecycle event to a hook and receive a structured
response. Its flat request shape and PascalCase `hook_event_name` values are
Claude-shaped for practical adapter compatibility, but it is not a Claude Code
wire-format specification.

The draft adds delivery, ordering, turn, operation, approval, model-request,
and delegation correlation that security telemetry needs. Hosts declare whether
each Core event is a `gate`, `observe`, `partial`, or `unavailable` capability;
they must not fabricate an event merely to claim support.

This is not a standard hook configuration format: discovery, matching, handler
execution, ordering, and native policy remain host concerns.

The human-readable documents in this directory are normative. The companion
JSON Schemas, fixtures, and examples make the JSON interchange testable.

## Documents

- [Core protocol](./core.md) defines the flat envelope, security correlation,
  Claude-shaped event-specific control responses, capability declarations,
  fail-open behavior, versioning, and conformance requirements.
- [Event registry](./events.md) defines the 13 Core PascalCase event names,
  their timing, required flat fields, and intended capability boundaries.
- [Extensions](./extensions.md) defines portable extension boundaries.
- [Security considerations](./security.md) defines data-handling and policy
  requirements.
- [Adapter guide](./adapters.md) maps the Claude Code baseline and defines
  requirements for other native hook facilities.

The draft is proposed by
[RFC 0001](https://github.com/trendmicro/agent-hook-standard/blob/main/rfcs/0001-agent-hook-core-event-contract.md).
It has not yet been accepted through the repository RFC process.
