---
sidebar_position: 3
---

# Event registry

Agent Hook 0.1 intentionally standardizes a small starter registry. A host MAY
support only the events it can observe reliably. Event types are lower-case,
dot-separated identifiers.

| Event type | When it occurs | Payload requirements | Decision-capable |
| --- | --- | --- | --- |
| `agent-hook.session.started` | A session begins or resumes. | A `source` string SHOULD describe startup, resume, or an equivalent native cause. | No |
| `agent-hook.session.ended` | A session terminates. | A `reason` string SHOULD describe the native end cause. | No |
| `agent-hook.tool.pre` | Immediately before a tool action begins. | `tool_call_id` and `tool.name` SHOULD be present; `tool.input` SHOULD contain the proposed arguments. | Yes |
| `agent-hook.tool.post` | After a tool action succeeds. | `tool_call_id`, `tool.name`, and `tool.output` SHOULD be present. | No |
| `agent-hook.tool.failed` | After a tool action fails. | `tool_call_id`, `tool.name`, and `error` SHOULD be present. | No |

The registry does not prescribe a tool-name namespace. A host SHOULD retain its
native tool name in `payload.tool.name`; adapters MAY add a normalized category
in `extensions` when one is available.

The registry is a starting point rather than a complete agent lifecycle model.
Prompt, model, permission, file, task, worktree, and context events are outside
0.1 and may be proposed through the RFC process.
