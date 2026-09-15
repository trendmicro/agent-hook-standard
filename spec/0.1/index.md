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

## Responsibilities and scope

| Participant | Contract responsibility |
| --- | --- |
| Host | Observe the defined boundary, declare faithful capabilities, and honor supported controls without bypassing native policy. |
| Adapter | Preserve the event's meaning and correlation while translating native callbacks and supported responses. It may be implemented inside the host. |
| Handler | Accept an event and return a schema-valid response correlated to that delivery. |

The registry distinguishes seven Gate events from eleven Observe events.
Control requires both a Gate event and a host declaration of `gate`; a faithful
observation alone does not provide preventive enforcement. The default for
missing or invalid handler responses is fail open, subject to independent
native restrictions. Completed model and tool results are Observe events, not
portable result-filtering or rollback boundaries.

The contract covers the lifecycle boundaries a host can expose faithfully.
It does not establish sandbox isolation or visibility into every internal
runtime or provider operation. Its per-delivery event and response semantics
do not define how multiple handlers compose. See the
[host obligations](./core.md#host-obligations) for existing responsibilities
and the boundaries that remain open in this draft.

## Reading the draft

The human-readable documents in this directory are normative. The companion
JSON Schemas, fixtures, and examples make the JSON interchange testable.
The website's [response reference](https://trendmicro.github.io/agent-hook-unity/responses)
and [capability guide](https://trendmicro.github.io/agent-hook-unity/capabilities)
are informative: they explain current requirements and limitations without
introducing a new response contract or capability configuration format.

## Documents

- [Core protocol](./core.md) defines the flat envelope, security correlation,
  Claude-shaped event-specific control responses, capability declarations,
  fail-open behavior, versioning, and conformance requirements.
- [Event registry](./events.md) defines the 18 Core PascalCase event names,
  their timing, required flat fields, and intended capability boundaries.
- [Extensions](./extensions.md) defines portable extension boundaries.
- [Security considerations](./security.md) defines data-handling and policy
  requirements.
- [Adapter guide](./adapters.md) maps the Claude Code baseline and defines
  requirements for other native hook facilities.

Network events describe application-level requests, including distinct retries
and redirects; memory events describe durable agent context;
`PreConfigChange` describes pending changes to agent behavior or capabilities.
Each event is part of the standard vocabulary, but hosts may declare support
independently. No enterprise service, signature, ledger, or remote approval
workflow is required. Older 0.1 schemas reject the new names; adopters must
update schemas and capability declarations before using the revised draft.

The original draft is proposed by
[RFC 0001](https://github.com/trendmicro/agent-hook-unity/blob/main/rfcs/0001-agent-hook-core-event-contract.md).
The five-event expansion is proposed by
[RFC 0004](https://github.com/trendmicro/agent-hook-unity/blob/main/rfcs/0004-standard-lifecycle-events.md).
Neither proposal has yet been accepted through the repository RFC process.

The separate [Responsible AI Agent Hooks project](https://responsibleai.github.io/agent-hooks/)
also uses the identifier `agent-hooks/0.1`. Its context and verdict documents
are not this draft's flat event and correlated response documents. Neither
that shared identifier nor the Claude-shaped field names imply wire
compatibility; the applicable schemas and semantics must be identified during
integration. This draft does not define automatic contract negotiation.
