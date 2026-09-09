---
sidebar_position: 2
---

# Core protocol

## Status and terminology

This document defines the Agent Hook 0.1 draft. The key words **MUST**,
**MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**,
and **OPTIONAL** in this document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they
appear in all capitals.

A **host** is the agent runtime that observes lifecycle activity. An
**adapter** translates between a host's native hook facility and this contract.
A **handler** consumes an Agent Hook event and returns an Agent Hook response.
An **invocation** is one host delivery of one event to one handler.

Agent Hook standardizes event and response documents, event semantics, and
capability declarations. It does not standardize handler discovery,
configuration files, matcher grammar, invocation order, process lifecycle,
timeout values, authentication, or a transport binding. A command handler
receiving one JSON document on standard input and writing one JSON response on
standard output is a useful non-normative adapter pattern.

## Event envelope

An event MUST be a JSON object that validates against the
[Hook Event schema](https://trendmicro.github.io/agent-hook-standard/schemas/0.1/hook-event.schema.json).
The 0.1 document shape is deliberately Claude-shaped: the event discriminator
is the flat `hook_event_name` member and Core event names are PascalCase. It is
not a byte-for-byte Claude Code payload or response contract.

Every event MUST contain these flat members:

| Member | Meaning |
| --- | --- |
| `spec` | The Agent Hook contract identifier, exactly `agent-hooks/0.1`. |
| `event_id` | A UUID that uniquely identifies this delivered event. |
| `hook_event_name` | A Core or extension event name. Core values are defined by the event registry. |
| `session_id` | An opaque identifier for the host session that emitted the event. |
| `timestamp` | RFC 3339 UTC (`Z`) time at which the host observed the event. |
| `sequence` | A non-negative integer ordering events emitted for the same `session_id`. |

For one session, a host MUST emit strictly increasing `sequence` values. A
re-delivery is a new event delivery and therefore has a new `event_id`; a host
MUST retain enough correlation data to identify the underlying occurrence.

Event-specific fields are flat top-level members. Core fields MUST NOT be
relocated into a generic `context` or `payload` object. A host SHOULD include
`cwd` when a meaningful current working directory exists, and SHOULD include
`transcript_path` when it safely exposes a transcript location. A host MUST
omit either member rather than fabricate a value. `agent_id`, `agent_type`,
`permission_mode`, `effort`, and `scratchpad_dir` MAY be included as flat
host-provided context.

The event registry identifies turn-scoped events. A turn-scoped event MUST
contain `prompt_id`, an opaque identifier shared by all events causally
attributable to the same caller-initiated turn. Session lifecycle events that
are not attributable to a turn MUST omit `prompt_id`; a host MUST NOT invent
one merely to satisfy a downstream consumer.

### Security correlation

`event_id` identifies a delivery, not the action or lifecycle operation that
caused it. The following event-specific identifiers provide the required
cross-event correlation:

| Identifier | Required event scope | Requirement |
| --- | --- | --- |
| `model_request_id` | `BeforeModelRequest`, `AfterModelResponse` | MUST identify one model request; the paired events MUST use the same value. |
| `operation_id` | `PermissionRequest`, `PermissionDenied` | MUST identify the operation that reached an approval boundary; the paired events MUST use the same value. |
| `permission_request_id` | `PermissionRequest`, `PermissionDenied` | MUST identify one native approval request; a denial MUST retain the request's value. |
| `delegation_id` | `SubagentStart`, `SubagentStop` | MUST identify one delegated subagent lifetime; the paired events MUST use the same value. |

When a host supplies a native tool-call identifier, such as Claude Code's
`tool_use_id`, an adapter SHOULD retain it as `tool_use_id`. At a permission
boundary, an adapter MUST create `operation_id` and `permission_request_id`
when the native runtime lacks them; it MUST NOT infer their correlation from
timing alone.

An event MAY contain `extensions`, as defined in the
[extension policy](./extensions.md). Hosts MUST preserve the correlation
members above when an event passes through an adapter or intermediate
component.

### Data minimization and redaction

Prompts, model messages, paths, tool arguments, tool results, and transcript
locations can contain sensitive data. A host MAY redact or omit data that it
cannot safely disclose. It MUST NOT fabricate a substitute value or silently
change a security-relevant target such that a handler's decision appears to
cover a different operation. If redaction prevents faithful observation,
correlation, or enforcement at the declared boundary, the host MUST declare
the event `partial` or `unavailable`, rather than `gate`.

## Response envelope

A handler response MUST be a JSON object that validates against the
[Hook Response schema](https://trendmicro.github.io/agent-hook-standard/schemas/0.1/hook-response.schema.json).
It contains required `spec` and `event_id` members. `event_id` MUST equal the
event's `event_id`; a response with a different identifier is invalid.

The response MAY contain the Claude-shaped common members `continue`,
`stopReason`, `systemMessage`, `terminalSequence`, `suppressOutput`, `async`,
`asyncTimeout`, `metadata`, and `extensions`. It MAY contain top-level
`decision: "block"`, but no top-level `allow`, `deny`, or `ask` value exists.
When top-level `decision` is present, `reason` is REQUIRED.

`hookSpecificOutput`, when present, MUST contain `hookEventName` equal to the
request's `hook_event_name`. Its control members are event-specific. They MUST
NOT be interpreted as a universal response decision.

| Core Gate | Control response | Effect |
| --- | --- | --- |
| `UserPromptSubmit` | Top-level `decision: "block"` with `reason`. | Prevents the accepted prompt from changing agent execution. |
| `BeforeModelRequest` | `hookSpecificOutput.permissionDecision`, optional `permissionDecisionReason`, and optional `updatedMessages`. | The permission decision controls the pre-dispatch request; `updatedMessages` replaces the messages at that boundary. |
| `PreToolUse` | `hookSpecificOutput.permissionDecision`, optional `permissionDecisionReason`, and optional `updatedInput`. | The permission decision controls the proposed tool use; `updatedInput` replaces the tool input at that boundary. |
| `PermissionRequest` | `hookSpecificOutput.decision.behavior`, with optional `updatedInput`, `updatedPermissions`, `message`, and `interrupt`. | The nested behavior controls the native approval request. |

For `BeforeModelRequest` and `PreToolUse`, `permissionDecision` is one of
`allow`, `deny`, `ask`, or `defer`. For `PermissionRequest`, nested
`decision.behavior` is `allow` or `deny`. An `allow` only passes that hook's
native gate; it MUST NOT override sandbox, organization, managed-policy, or
user-approval restrictions.

Agent Hook control semantics are portable; native response documents are not.
An adapter MUST interpret a control response only for a Core event classified as
a Gate by the event registry and declared `gate` by the host. It MUST NOT claim
universal Claude Code response compatibility. Claude Code uses event-specific
response shapes, and it emits neither `BeforeModelRequest` nor
`AfterModelResponse`; a model-response mapping requires a future profile or a
new host-specific mapping.

For an `observe` event, top-level `decision` and all control members in
`hookSpecificOutput` MUST be ignored for control purposes. A host MAY retain
them as diagnostic or observational data. A `partial` or `unavailable`
capability MUST NOT emit a normalized Core event.

## Fail-open behavior

An absent response, invalid JSON, schema-invalid response, correlation
mismatch, handler error, or timeout MUST result in no Agent Hook control result.
A host that declared the event `gate` MUST continue the affected operation
unless an independent native policy blocks it. Adapters SHOULD emit a diagnostic
record containing the event ID, hook event name, failure class, and handler
identity without retaining sensitive event data.

This requirement controls only Agent Hook 0.1. It does not weaken host,
sandbox, administrative, or organization policy. A host requiring fail-closed
enforcement MUST use a native mechanism or a future explicitly configured
profile; it MUST NOT reinterpret an Agent Hook failure as an implicit block
while claiming 0.1 default behavior.

## Versioning and conformance

`spec` is a major/minor contract identifier. A 0.1 implementation MUST emit and
accept exactly `agent-hooks/0.1`; patch-only specification changes do not change
the member. Future incompatible envelopes require a new major version.

A host claiming 0.1 conformance MUST publish a capability declaration that
enumerates every Core `hook_event_name` in the event registry. For each name,
the declaration MUST state exactly one of these modes:

| Mode | Meaning |
| --- | --- |
| `gate` | The host emits the event before the relevant irreversible operation and enforces a valid Agent Hook decision. |
| `observe` | The host emits a faithful event, but a handler response cannot control the operation. |
| `partial` | The host has a related native signal but cannot faithfully meet one or more required timing, field, correlation, control, or privacy semantics. The declaration MUST identify the limitation, and the host MUST NOT emit the signal as a normalized Core event. |
| `unavailable` | The host cannot emit the event faithfully. |

A host MUST NOT fabricate a Core event to improve its declaration. It MUST NOT
declare `gate` when the native timing is post-effect, a response cannot be
enforced, redaction removes the security-relevant information needed for the
declared boundary, or the event registry classifies the event as Observe.

An implementation conforms as an **event producer** if it emits schema-valid
events, publishes an accurate capability declaration, and implements this
document's required semantics. It conforms as a **handler** if it accepts
schema-valid events and emits schema-valid correlated responses. An **adapter**
conforms if it preserves core semantics and correlation while mapping between a
native hook facility and the event/response contract. Conformance does not
imply compatibility with a vendor's configuration file or response envelope.
