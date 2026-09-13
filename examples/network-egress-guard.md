# Network Egress & SSRF Security Guard

This non-normative example handles the `PreNetworkAccess` Gate (**Security Defense Gate 7**). It intercepts outbound socket or HTTP requests initiated by an agent and blocks Server-Side Request Forgery (SSRF) attempts targeting cloud instance metadata or private enterprise subnets.

## Security Receiver Handler (Node.js)

```javascript
#!/usr/bin/env node
import process from 'node:process';
import { isIP } from 'node:net';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const event = JSON.parse(input);

const host = event.destination_host ?? '';
const port = event.destination_port ?? 0;

const response = {
  spec: 'agent-hooks/0.1',
  event_id: event.event_id,
  hookSpecificOutput: {
    hookEventName: 'PreNetworkAccess'
  }
};

function isPrivateOrCloudMetadata(destination) {
  // Block AWS/GCP/Azure link-local metadata address
  if (destination === '169.254.169.254') return true;

  // Block localhost
  if (destination === 'localhost' || destination === '127.0.0.1' || destination === '::1') return true;

  // Block RFC 1918 private subnets
  if (/^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)/.test(destination)) return true;

  return false;
}

if (isPrivateOrCloudMetadata(host)) {
  response.hookSpecificOutput.permissionDecision = 'deny';
  response.hookSpecificOutput.permissionDecisionReason =
    `Access to internal network or cloud metadata (${host}:${port}) is prohibited by enterprise zero-trust policy.`;
} else {
  response.hookSpecificOutput.permissionDecision = 'allow';
}

process.stdout.write(JSON.stringify(response) + '\n');
```

## Normative Effect

- An `allow` verdict permits the runtime or network sandbox to establish the connection.
- A `deny` verdict immediately aborts socket creation or drops the packet with an access denied error.

See the [Event Registry](../spec/0.1/events.md), [Security Considerations](../spec/0.1/security.md), and [RFC 0002](../rfcs/0002-enterprise-security-defense-gates.md) for full protocol semantics.
