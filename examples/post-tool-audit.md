# Post-tool audit event

This non-normative example records a successful tool invocation without
attempting to control it. A decision in a response to `agent-hook.tool.post` is
ignored by the protocol, so the handler returns annotations only.

Event delivered by the adapter:

```json
{
  "hook_version": "0.1",
  "event_id": "862a966f-6f7b-4c15-a8c5-40df353eeaac",
  "event_type": "agent-hook.tool.post",
  "timestamp": "2026-09-09T10:17:00Z",
  "context": { "session_id": "session-42" },
  "payload": {
    "tool_call_id": "call-17",
    "tool": {
      "name": "shell",
      "output": { "exit_code": 0 }
    }
  }
}
```

Response from the audit handler:

```json
{
  "hook_version": "0.1",
  "event_id": "862a966f-6f7b-4c15-a8c5-40df353eeaac",
  "annotations": {
    "audit_status": "recorded",
    "retention_class": "30d"
  }
}
```

Handlers should not copy raw prompts, tool arguments, outputs, or credentials
into audit records unless a documented privacy policy permits it.
