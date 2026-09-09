---
sidebar_position: 6
---

# Adapter guide

An adapter maps a host's native hook events and results to flat Agent Hook
documents. It does not make a host's settings file, matcher language, execution
order, transport, or native response envelope part of this specification.

## Claude Code reference mapping

The following table identifies the direct Claude Code baseline where one
exists. A dash means Claude Code does not emit a faithful native event; an
adapter MUST declare that Core event `unavailable` rather than fabricate it.

| Agent Hook `hook_event_name` | Claude Code event | Adapter requirement |
| --- | --- | --- |
| `SessionStart` | `SessionStart` | Preserve the native session ID and source; add the standard delivery and sequence fields. |
| `UserPromptSubmit` | `UserPromptSubmit` | Preserve `prompt`; retain its native `prompt_id` as the turn correlation. |
| `BeforeModelRequest` | — | Declare `unavailable`; do not derive it from model selection or tool activity. |
| `AfterModelResponse` | — | Declare `unavailable`; do not synthesize it from streamed display output or a later tool event. |
| `PreToolUse` | `PreToolUse` | Map `tool_name`, `tool_input`, and `tool_use_id`. |
| `PermissionRequest` | `PermissionRequest` | Map the native request and assign both `operation_id` and `permission_request_id`. Claude Code does not supply `tool_use_id` here. |
| `PermissionDenied` | `PermissionDenied` | Preserve the native reason and tool-call ID when supplied; retain the corresponding operation and permission-request identifiers. |
| `PostToolUse` | `PostToolUse` | Preserve structured `tool_response`, tool input, and tool-call ID. |
| `PostToolUseFailure` | `PostToolUseFailure` | Preserve `error`, interruption information, and duration when supplied. |
| `SubagentStart` | `SubagentStart` | Assign `delegation_id`; preserve native agent ID and type. |
| `SubagentStop` | `SubagentStop` | Retain the `delegation_id` assigned at start and the native outcome context. |
| `Stop` | `Stop` | Preserve the active turn's `prompt_id` when the stop is turn-scoped. |
| `SessionEnd` | `SessionEnd` | Preserve the native end reason. |

The exact native availability and payload vary by product and release. An
adapter for another host MUST map only events it can implement faithfully and
MUST publish its own `gate`, `observe`, `partial`, or `unavailable` capability
declaration. It MUST identify any timing, field, correlation, response, or
privacy limitation for a `partial` mapping.

## Envelope and correlation mapping

An adapter MUST construct the standard flat envelope: `spec`, `event_id`,
`hook_event_name`, `session_id`, `timestamp`, and `sequence`. It SHOULD retain
native `cwd` and `transcript_path` when safely available, and MUST omit them
rather than invent them. It MUST retain `prompt_id` for a turn-scoped native
event.

Native identifiers do not remove the standard correlation requirements. An
adapter MUST assign and retain `model_request_id`, `operation_id`,
`permission_request_id`, and `delegation_id` wherever the Core protocol
requires them. In particular, it MUST not attempt to correlate Claude Code's
`PermissionRequest` with a later tool event solely from timing, because the
native request has no `tool_use_id`.

An adapter MAY redact data before delivery to a handler. It MUST preserve the
meaning and correlation of the exposed event, and MUST downgrade the capability
to `partial` or `unavailable` when redaction prevents faithful security
observation or enforcement.

## Response mappings

The Agent Hook response is Claude-shaped and event-specific, not a universal
allow/deny/ask decision document. An adapter MUST interpret a control response
only at an event classified as a Gate by the registry, declared `gate`, and
reached through a native control point that has not passed the relevant effect
boundary.

| Core Gate | Standard response shape | Claude Code direction |
| --- | --- | --- |
| `UserPromptSubmit` | Top-level `decision: "block"` plus `reason`. | Map to Claude Code's prompt block response. |
| `BeforeModelRequest` | `hookSpecificOutput` with `hookEventName`, `permissionDecision`, optional `permissionDecisionReason`, and optional `updatedMessages`. | Claude Code has no native event; declare it `unavailable` rather than fabricate a mapping. |
| `PreToolUse` | `hookSpecificOutput` with `hookEventName`, `permissionDecision`, optional `permissionDecisionReason`, and optional `updatedInput`. | Map to Claude Code's `PreToolUse` permission decision. |
| `PermissionRequest` | `hookSpecificOutput.decision.behavior`, with optional input, permission, message, and interrupt updates. | Map to Claude Code's nested permission-request decision. |

`permissionDecision` uses `allow`, `deny`, `ask`, or `defer`; nested
`decision.behavior` uses `allow` or `deny`. A response with
`hookSpecificOutput` MUST use a `hookEventName` that matches the request. An
adapter MUST NOT let an allow result override native or organization policy.

Top-level `decision: "block"` and all `hookSpecificOutput` control members are
ignored for an Observe event. Claude Code's other response shapes are likewise
event-specific: `PostToolUse`, for example, can replace model-visible output
only after the effect completed, and `Stop` blocking has a native retry limit.
Those facts do not make either event an Agent Hook `gate`. No universal Claude
Code response compatibility is claimed, and no Claude mapping exists for the
two model events in 0.1.

Adapters MUST correlate the native invocation with `event_id` and MUST apply the
core fail-open rule to absent, invalid, timed-out, or errored Agent Hook
responses. A product's independently configured native behavior may be stricter
but is not Agent Hook 0.1 behavior.

## Non-normative stdio adapter pattern

A common adapter serializes one event object to a command handler's standard
input and reads at most one response object from standard output. Standard error
is reserved for diagnostics. This pattern is compatible with the general shape
of Claude Code and Gemini CLI command hooks, but the process launch command,
timeout, settings location, matcher, and output parsing details remain native
to each host.
