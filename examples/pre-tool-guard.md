# Pre-tool security guard

This non-normative example shows a handler for
`agent-hook.tool.pre`. A host adapter can deliver the event as JSON on standard
input and use the single JSON response on standard output.

```javascript
#!/usr/bin/env node
import process from 'node:process';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const event = JSON.parse(input);
const command = event.payload?.tool?.input?.command ?? '';

const response = {
  hook_version: '0.1',
  event_id: event.event_id
};

if (/\brm\s+-rf\b/.test(command)) {
  response.decision = 'deny';
  response.reason = 'Destructive recursive deletion is blocked.';
} else if (/\bdeploy\b.*\bproduction\b/i.test(command)) {
  response.decision = 'ask';
  response.reason = 'Confirm the production deployment.';
} else {
  response.decision = 'allow';
}

process.stdout.write(`${JSON.stringify(response)}\n`);
```

`allow` only passes this guard; a host's sandbox or managed policy can still
block the action. `ask` requires a native approval workflow, and a
non-interactive host must deny it. See the [core protocol](../spec/0.1/core.md)
for the normative behavior.
