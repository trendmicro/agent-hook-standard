---
sidebar_position: 4
---

# Asynchronous Human-in-the-Loop (HITL) & Resumption Protocol

## Status and Purpose

This document defines the normative protocol for **Asynchronous Human-in-the-Loop (HITL) Authorization and Turn Resumption** in Agent Hook 0.1. It specifies the interaction pattern triggered when a security receiver (Policy Decision Point, PDP) returns `permissionDecision: "ask"` at a gating lifecycle boundary (such as `PreToolUse`, `PermissionRequest`, or `PreNetworkAccess`).

Sub-second agent execution budgets inevitably conflict with human managerial decision latency (minutes to hours). This protocol decouples synchronous event evaluation from human review without causing network timeouts, agent crashes, or Time-of-Check to Time-of-Use (TOCTOU) execution tampering.

## Core Architecture

```
+---------------+      1. PreToolUse      +--------------------+      2. Eval       +---------------+
| Agent Runtime | ----------------------> |  Approval Gateway  | -----------------> |  Security PDP |
|     (PEP)     | <---------------------- |   (State Broker)   | <----------------- | (Policy Engine|
+---------------+   3. Turn Suspended     +--------------------+   decision: "ask"  +---------------+
        |              (HTTP 202/SSE)               |               escalation info
        |                                           | 4. Escalate
        |                                           v
        |                                 +--------------------+
        |                                 | Approver (Slack /  |
        |                                 | Teams / ServiceNow)|
        |                                 +--------------------+
        |                                           | 5. Human Decision
        |        6. Resumption Webhook / SSE        v
        +========================================== +
                 (Signed ApprovalGrantToken)
```

## Protocol Workflow

### 1. Suspension Initiation (`decision: "ask"`)

When a hook invocation encounters an action requiring human approval, the security receiver MUST respond with:
- `permissionDecision: "ask"` (within `hookSpecificOutput`)
- An `escalation` object containing:
  - `challenge_id`: A unique string identifying this approval transaction.
  - `approval_url`: An HTTPS URL where human approvers inspect context and render a decision.
  - `timeout_seconds`: An integer specifying how long the agent will hold suspended state before timing out (e.g. 3600 seconds).
  - `channels`: An optional array of destination notification platforms (`["slack", "teams", "email", "itsm"]`).

Upon receiving `decision: "ask"`, the runtime (PEP):
1. Freezes the active turn execution loop for the affected tool invocation.
2. Transitions the turn into `SUSPENDED` state.
3. If running over HTTP/gRPC, the gateway returns HTTP `202 Accepted` to the upstream caller, maintaining connection state via Server-Sent Events (SSE) or a persistent webhook listener.

### 2. Escalation Delivery

The Approval Gateway formats the suspended request into an enterprise notification card (e.g. Slack Block Kit, Microsoft Teams Adaptive Cards) displaying:
- Initiating Agent Identity (`actor.subject`, `agent_id`)
- Target tool name and sanitized arguments
- Target destination / network host (if applicable)
- Cryptographic hash (`content_identity`)
- Decision buttons: `[Approve]` and `[Deny]`

### 3. The Approval Grant Token (`ApprovalGrantToken`)

Upon human approval, the Policy Decision Point mints a cryptographically signed `ApprovalGrantToken` (JWT or Ed25519-signed JSON structure) containing:
- `grant_id`: UUIDv7 unique token identifier.
- `challenge_id`: Matching the original escalation challenge.
- `session_id`: Matching the agent session.
- `tool_use_id`: Matching the specific tool call.
- `content_identity`: Exactly matching `sha256:<hex>` of the approved tool arguments.
- `approved_by`: Identity of the human reviewer.
- `expires_at`: Strict expiration timestamp (SHOULD NOT exceed 300 seconds from issuance).

### 4. Turn Resumption & Deterministic TOCTOU Verification

The Approval Gateway delivers the `ApprovalGrantToken` back to the Agent Runtime via:
- **Inbound Webhook**: For enterprise cloud runtimes (`POST /v1/agent/resume`).
- **Long-Lived SSE Stream**: For firewalled local developer CLIs (Claude Code, Gemini CLI).

#### Mandatory 1-Microsecond Pre-Dispatch TOCTOU Check

Before executing the tool, the Agent Runtime MUST perform a deterministic verification in memory:

```python
# Deterministic 1-µs Verification Rule
assert token.content_identity == compute_jcs_sha256(staged_tool_input), "TOCTOU_TAMPER_DETECTED"
assert current_timestamp() <= token.expires_at, "APPROVAL_GRANT_EXPIRED"
assert token.session_id == runtime.session_id, "CROSS_SESSION_REPLAY"
```

If the memory buffer or on-disk file was modified while waiting for human approval, `token.content_identity` will not match the staged payload. The runtime MUST immediately abort execution, emit a tamper alert, and fail closed.
