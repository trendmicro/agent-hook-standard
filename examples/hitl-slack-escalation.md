# Asynchronous Human-in-the-Loop (HITL) Slack Escalation

This non-normative example handles the `PreToolUse` Gate when a high-risk operation requires managerial dual-custody approval. It illustrates how a security receiver returns `permissionDecision: "ask"` with an `escalation` payload, suspends the turn, and later verifies the cryptographic `ApprovalGrantToken` upon resumption.

## Security Receiver Handler (Node.js)

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

// Check if the command modifies cloud infrastructure or production databases
if (/terraform\s+apply|kubectl\s+delete|drop\s+database/i.test(command)) {
  const challengeId = `chal_${Date.now()}`;
  
  response.hookSpecificOutput.permissionDecision = 'ask';
  response.hookSpecificOutput.permissionDecisionReason =
    'Production-impacting command detected; managerial authorization required.';
  response.hookSpecificOutput.escalation = {
    challenge_id: challengeId,
    approval_url: `https://security.enterprise.corp/approvals/${challengeId}`,
    timeout_seconds: 1800,
    channels: ['slack', 'teams']
  };
} else {
  response.hookSpecificOutput.permissionDecision = 'allow';
}

process.stdout.write(JSON.stringify(response) + '\n');
```

## Runtime TOCTOU Verification on Resumption (Python)

Upon receiving human approval via Slack, the Approval Gateway sends an `ApprovalGrantToken` to the Agent Runtime. Before dispatching the tool, the runtime performs the mandatory 1-microsecond pre-dispatch check:

```python
import hashlib
import json

def verify_and_dispatch(staged_tool_input, grant_token):
    # 1. Canonicalize staged input per RFC 8785 (JCS)
    canonical_bytes = json.dumps(staged_tool_input, sort_keys=True, separators=(',', ':')).encode('utf-8')
    computed_digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"

    # 2. Verify token cryptographic binding
    assert grant_token["content_identity"] == computed_digest, "FATAL: TOCTOU bait-and-switch tamper detected!"
    assert grant_token["expires_at"] >= current_epoch_seconds(), "FATAL: Approval grant has expired!"

    # 3. Dispatch tool safely
    return execute_tool(staged_tool_input)
```

See the [Asynchronous HITL Specification](../spec/0.1/hitl.md) and [RFC 0003](../rfcs/0003-agent-hitl-resumption-protocol.md) for full protocol semantics.
