# Pre-tool security guard

This non-normative example handles the `PreToolUse` Gate. A host adapter may
deliver the request as JSON on standard input and consume one JSON response on
standard output.

```javascript
#!/usr/bin/env node
import process from 'node:process';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const event = JSON.parse(input);
const command = event.tool_input?.command ?? '';

const response = {
  spec: 'agent-hooks/0.1',
  event_id: event.event_id,
  hookSpecificOutput: {
    hookEventName: 'PreToolUse'
  }
};

if (/\brm\s+-rf\b/.test(command)) {
  response.hookSpecificOutput.permissionDecision = 'deny';
  response.hookSpecificOutput.permissionDecisionReason =
    'Destructive recursive deletion is blocked.';
} else if (/\bdeploy\b.*\bproduction\b/i.test(command)) {
  response.hookSpecificOutput.permissionDecision = 'ask';
  response.hookSpecificOutput.permissionDecisionReason =
    'Confirm the production deployment.';
} else {
  response.hookSpecificOutput.permissionDecision = 'allow';
}

process.stdout.write(JSON.stringify(response) + '\n');
```

The `PreToolUse` response uses Claude Code's
`hookSpecificOutput.permissionDecision` convention. An `allow` only passes
this hook's gate; a sandbox, organization policy, host policy, or native
approval flow can still block the action. `ask` requires host-native approval.
See the [core protocol](../spec/0.1/core.md) for the normative behavior.
