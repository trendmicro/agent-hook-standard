---
sidebar_position: 6
---

# Adapter guide

An adapter maps a host's native hook events and results to Agent Hook documents.
It does not make a host's settings file, matcher language, execution order, or
transport part of this specification.

## Representative lifecycle mappings

| Agent Hook event | Claude Code | Cursor | Gemini |
| --- | --- | --- | --- |
| `agent-hook.session.started` | `SessionStart` | `sessionStart` | `SessionStart` when available |
| `agent-hook.session.ended` | `SessionEnd` | `sessionEnd` | `SessionEnd` when available |
| `agent-hook.tool.pre` | `PreToolUse` | `preToolUse` / `before*Execution` | `BeforeTool` / `pre_tool_execution` |
| `agent-hook.tool.post` | `PostToolUse` | `postToolUse` / `after*Execution` | `AfterTool` / `post_tool_execution` |
| `agent-hook.tool.failed` | `PostToolUseFailure` | `postToolUseFailure` | Native failure detail on a post-tool event, if available |

The exact native event availability and payload vary by product and release.
An adapter MUST omit a mapping it cannot implement faithfully rather than
fabricating a core event.

## Response mappings

| Agent Hook decision | Claude Code direction | Cursor direction | Gemini direction |
| --- | --- | --- | --- |
| `allow` | Map to its native allow/continue decision when available; never bypass host policy. | Map to a native allow/continue result when available. | Map to `allow` for a pre-tool hook. |
| `deny` | Map to a blocking permission/decision result with `reason`. | Map to a blocking result with `reason`. | Map to `deny` with `reason`. |
| `ask` | Map to the native permission prompt/ask path. | Map to the native approval path when available. | Use its approval path when available; otherwise deny in non-interactive use. |

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
