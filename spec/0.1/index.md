---
sidebar_position: 1
slug: /0.1
---

# Agent Hook 0.1 draft

Agent Hook 0.1 is a draft portable contract for an agent runtime to deliver a
lifecycle event to a hook and receive a structured response. This is not a
standard hook configuration format: discovery, matching, handler execution,
ordering, and native policy remain host concerns.

The human-readable documents in this directory are normative. The companion
JSON Schemas, fixtures, and examples make the JSON interchange testable.

## Documents

- [Core protocol](./core.md) defines the envelope, responses, control behavior,
  versioning, and conformance requirements.
- [Event registry](./events.md) defines the deliberately small initial event
  set.
- [Extensions](./extensions.md) defines portable extension boundaries.
- [Security considerations](./security.md) defines data-handling and policy
  requirements.
- [Adapter guide](./adapters.md) maps representative Claude Code, Cursor, and
  Gemini hooks into this contract.

The draft is proposed by
[RFC 0001](https://github.com/trendmicro/agent-hook-standard/blob/main/rfcs/0001-agent-hook-core-event-contract.md).
It has not yet been accepted through the repository RFC process.
