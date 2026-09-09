---
sidebar_position: 3
---

# Event registry

This document defines the Core event registry for the Agent Hook 0.1 draft.
The capitalized key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**,
**SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are
to be interpreted as described in the [Core protocol](./core.md).

The registry adopts the flat request shape and `hook_event_name` spelling used
by Claude Code hook requests. It standardizes portable lifecycle boundaries;
it does not require a host to manufacture a callback that its native runtime
does not expose.

## Event name and request shape

Every Core event MUST be a flat request object that validates against the Hook
Event schema. `hook_event_name` is its sole event discriminator and MUST equal
one of the PascalCase Core values in this document. `event_type`, a generic
`payload` wrapper, and a second event discriminator MUST NOT appear in a
normalized Agent Hook 0.1 request.

The shared request envelope is defined by the Core protocol and schema. In
addition to those shared fields, each Core event MUST contain the
event-specific fields listed below. `cwd`, `transcript_path`, and other
host-native context MUST be omitted when unavailable rather than invented.

## Core event registry

The classification in the final column describes the standard boundary, not
merely whether an individual host happens to deliver a callback.

Unless a requirement specifically says otherwise, the per-event requirements
apply when a producer declares that event as `gate` or `observe`. A `partial`
or `unavailable` capability MUST NOT be represented as a Core event delivery;
an extension MAY expose related native data without claiming Core semantics.

| `hook_event_name` | Exact lifecycle boundary | Required event-specific fields | Classification |
| --- | --- | --- | --- |
| `SessionStart` | When a host starts, resumes, clears, compacts, or forks a session context before subsequent agent work. | `source` | Observe |
| `UserPromptSubmit` | After an external prompt is accepted, but before it affects agent execution. | `prompt`, `prompt_id` | Gate |
| `BeforeModelRequest` | Immediately before a complete request is dispatched to a model provider. | `prompt_id`, `model_request_id`, `model`, `messages` | Gate |
| `AfterModelResponse` | Once the terminal result of one complete model request is available. | `prompt_id`, `model_request_id`, `model`, `outcome`, and `response` on success or `error` otherwise | Observe |
| `PreToolUse` | Immediately before a tool begins and before any effect of that invocation occurs. | `prompt_id`, `tool_name`, `tool_input`, `tool_use_id` | Gate |
| `PermissionRequest` | At a native approval boundary, before the requested operation has been allowed or denied. | `prompt_id`, `permission_request_id`, `operation_id`, `operation` | Gate |
| `PermissionDenied` | After a user, policy, handler, or host denies a requested operation. | `prompt_id`, `permission_request_id`, `operation_id`, `reason`, `denied_by` | Observe |
| `PostToolUse` | After one tool invocation completes successfully. | `prompt_id`, `tool_name`, `tool_input`, `tool_response`, `tool_use_id` | Observe |
| `PostToolUseFailure` | After one tool invocation fails or is interrupted. | `prompt_id`, `tool_name`, `tool_input`, `tool_use_id`, `error` | Observe |
| `SubagentStart` | Before a child agent receives executable work. | `prompt_id`, `delegation_id`, `agent_id`, `agent_type`, `parent_agent_id` | Observe |
| `SubagentStop` | After a child agent reaches a terminal state. | `prompt_id`, `delegation_id`, `agent_id`, `agent_type`, `outcome` | Observe |
| `Stop` | At the terminal boundary of a caller-initiated, prompt-scoped turn. | `prompt_id`, `outcome` | Observe |
| `SessionEnd` | After final output, or after an observable abnormal session termination. | `reason` | Observe |

### `SessionStart`

A producer MUST emit `SessionStart` before subsequent agent work for the
applicable start, resume, clear, compaction, or fork. `source` MUST identify
the cause. Producers SHOULD use `startup`, `resume`, `clear`, `compact`,
`fork`, or `other`; a richer native cause MAY be preserved in `extensions`.
A change of model within an existing session MUST NOT be represented as
`SessionStart`.

### `UserPromptSubmit`

A producer MUST emit `UserPromptSubmit` only after an external prompt has been
accepted and before that prompt changes agent execution. `prompt_id` identifies
the resulting prompt-scoped turn. A host that rejects input before accepting it
MUST NOT represent that rejected input as `UserPromptSubmit`.

### `BeforeModelRequest`

A producer MUST emit `BeforeModelRequest` immediately before dispatching a
complete request to the model provider. `messages` MUST represent the complete
request content visible at that boundary, subject to the privacy rules below.
The event is not a model-selection notification and MUST NOT be emitted merely
because the host selected, configured, or displayed a model.

### `AfterModelResponse`

A producer MUST emit exactly one `AfterModelResponse` for each terminal model
request result it observes. `model_request_id` MUST equal the identifier from
the corresponding `BeforeModelRequest`. `outcome` MUST identify the terminal
condition. A successful outcome MUST include `response`; a non-successful
outcome MUST include `error`. A streaming delta, partial token, or display
callback MUST NOT be represented as `AfterModelResponse`.

### `PreToolUse`

A producer MUST emit `PreToolUse` before the identified invocation begins and
before any effect of the invocation occurs. `tool_name` and `tool_input` MUST
describe the proposed invocation, and `tool_use_id` MUST be stable for its
life. A host that can observe a tool only after it begins MUST NOT claim this
event as a faithful Gate.

### `PermissionRequest`

A producer MUST emit `PermissionRequest` when an operation reaches the host's
native approval boundary and before that request is resolved. `operation` MUST
be an object containing at least `kind` and `name`; it MAY contain `input`.
Approval is not limited to tools, so this event MUST NOT require
`tool_use_id`. When the operation is a tool and the corresponding fields are
available, a producer SHOULD include `tool_name`, `tool_input`, and
`tool_use_id` as compatible additional fields.

### `PermissionDenied`

A producer MUST emit `PermissionDenied` after a concrete approval request is
denied. It MUST retain the `permission_request_id` and `operation_id` from the
corresponding `PermissionRequest`. `denied_by` MUST identify the actor or
authority that denied the operation, such as a user, policy, handler, or host.
`PermissionDenied` is independent audit evidence: a consumer MUST NOT infer it
from the absence of a later tool event.

### `PostToolUse`

A producer MUST emit `PostToolUse` after a tool invocation completes
successfully. Its `tool_use_id` MUST equal the identifier on the corresponding
`PreToolUse`, and `tool_response` MUST be the terminal result available to the
host. `duration_ms` MAY be included when the host can calculate it faithfully.

### `PostToolUseFailure`

A producer MUST emit `PostToolUseFailure` after a tool invocation fails or is
interrupted. Its `tool_use_id` MUST equal the identifier on the corresponding
`PreToolUse`, and `error` MUST describe the terminal failure available to the
host. A producer MAY include the Claude-compatible `is_interrupt` and
`duration_ms` fields when it can provide them faithfully. For one `tool_use_id`,
`PostToolUse` and `PostToolUseFailure` are mutually exclusive terminal
outcomes.

### `SubagentStart`

A producer MUST emit `SubagentStart` before the identified child agent receives
executable work. `agent_id` identifies the child and `parent_agent_id`
identifies its parent. `delegation_id` identifies this delegation, not merely
the lifetime of the child process or agent instance.

### `SubagentStop`

A producer MUST emit `SubagentStop` after the child agent identified by
`agent_id` reaches a terminal state. It MUST retain the `delegation_id` from
the matching `SubagentStart`; `outcome` MUST identify that terminal state. A
child-agent terminal event MUST NOT be represented as the parent's `Stop`.

### `Stop`

A producer MUST emit `Stop` at the terminal boundary for a caller-initiated,
prompt-scoped turn. It MUST retain the `prompt_id` from the corresponding
`UserPromptSubmit`. `outcome` MUST identify the terminal state. `Stop` is not
a session termination event and MUST NOT replace `SessionEnd`.

### `SessionEnd`

A producer MUST emit `SessionEnd` after final output or when it can observe an
abnormal session termination. `reason` MUST describe the end cause available
to the host. If a host cannot observe an abnormal termination, it MUST declare
that limitation rather than fabricate `SessionEnd`.

## Gate and Observe semantics

A **Gate** is a boundary at which a handler's response may be considered before
the host crosses the stated lifecycle boundary. A host MUST deliver a Gate in
time to enforce its response; otherwise it MUST report the event as `partial`
or `unavailable`, not as a Gate. A response that permits an operation only
passes the Agent Hook gate and MUST NOT override a native sandbox, organization
policy, host policy, or user approval.

An **Observe** event records a lifecycle boundary without making the event a
portable control point. A host MUST NOT use a handler response to retroactively
change an observed action while claiming conformance to this registry.

## Correlation and ordering

`event_id` identifies a single delivery to a single handler. It MUST NOT be
used in place of an action or lifecycle correlation identifier.

- `model_request_id` correlates `BeforeModelRequest` with
  `AfterModelResponse`.
- `tool_use_id` correlates `PreToolUse` with exactly one terminal
  `PostToolUse` or `PostToolUseFailure` when a terminal result is observed.
- `permission_request_id` and `operation_id` correlate `PermissionRequest`
  with `PermissionDenied`.
- `delegation_id` correlates `SubagentStart` with `SubagentStop`.
- `prompt_id` correlates `UserPromptSubmit` with `Stop`.

The shared `session_id` scopes a session. The shared `sequence` field MUST
increase strictly within that session, so that consumers can order events even
when timestamps collide or are imprecise. An adapter or intermediate component
MUST preserve correlation identifiers and MUST NOT reuse them for a different
logical action.

## Sensitive content and telemetry

Prompts, model messages, tool input, tool responses, errors, workspace paths,
and transcript locations can contain sensitive information. A producer MUST
apply its applicable data-handling policy before delivering these fields to a
handler or telemetry destination.

When a producer omits, truncates, tokenizes, or replaces sensitive content, it
MUST declare that redaction by a schema-supported or namespaced extension
member, and it MUST NOT fabricate substitute content. A consumer MUST treat a
declared-redacted value as incomplete and MUST NOT assume it is the original
request, response, or tool result.

## Capability declaration

A host or adapter MUST declare the fidelity of every Core event as one of the
following values. The declaration's transport and configuration format are
outside the scope of Agent Hook 0.1.

| Capability | Meaning |
| --- | --- |
| `gate` | The host observes the exact pre-action boundary and can enforce a handler response there. |
| `observe` | The host faithfully observes the registry boundary, but it is not a portable control point. |
| `partial` | The host can expose a related native callback but cannot preserve the registry boundary, required data, or control semantics. The declaration MUST identify the limitation, and the callback MUST NOT be emitted as a Core event. |
| `unavailable` | The host cannot expose the event faithfully. It MUST NOT emit a fabricated equivalent. |

A host MAY support only the Core events it can implement faithfully. It MUST
not label an after-the-fact notification as a pre-action Gate, and it MUST not
claim that an omitted callback is equivalent to a Core event.

## Deferred and extended events

The following are not Core in Agent Hook 0.1: network access, file changes,
worktree lifecycle, compaction, UI and message-display activity, reasoning,
and task-management events. They MAY be specified as extensions under the
[extension policy](./extensions.md), but an extension MUST NOT claim Core
semantics unless a future version adds it to this registry.

`NetworkAccessRequest` remains deferred pending a dedicated network-gateway
profile. Current runtimes differ between a genuine preflight gate, a tool
approval, and an after-the-fact notification; therefore it MUST NOT be treated
as a portable Core Gate in 0.1.
