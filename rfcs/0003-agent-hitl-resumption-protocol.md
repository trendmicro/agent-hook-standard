---
title: "RFC 0003: Agent Asynchronous Human-in-the-Loop (HITL) Authorization & Resumption Protocol"
status: Draft
discussion: "https://github.com/trendmicro/agent-hook-standard/discussions/TBD-0003"
review-start: TBD
review-end: TBD
maintainer-votes: []
decision: "Pending"
supersedes: []
superseded-by: []
---

# RFC 0003: Agent Asynchronous Human-in-the-Loop (HITL) Authorization & Resumption Protocol

## Summary

This RFC proposes the **Asynchronous Human-in-the-Loop (HITL) Authorization and Turn Resumption Protocol** for Agent Hook 0.1. It establishes a vendor-neutral, non-blocking workflow when a hook evaluation returns `permissionDecision: "ask"`. It defines the Approval Gateway role, non-blocking turn suspension via HTTP 202 / Server-Sent Events (SSE), multi-channel enterprise escalation (Slack, Microsoft Teams, ServiceNow), the cryptographic `ApprovalGrantToken`, and a mandatory 1-microsecond pre-dispatch Time-of-Check to Time-of-Use (TOCTOU) verification check.

## Motivation

Sub-second agent execution latency budgets conflict directly with human managerial decision timescales (which range from minutes to hours). Synchronously holding open HTTP/gRPC connections while waiting for human review results in socket timeouts, connection pool exhaustion, and agent turn crashes.

Furthermore, post-approval TOCTOU execution tampering presents a fatal vulnerability: if an agent requests approval for a benign command (`kubectl get pods`), and while waiting for approval in Slack, a compromised subagent or parallel thread alters the staged buffer to `kubectl delete namespace prod`, naive runtimes execute the modified command because the human approval was not cryptographically bound to the specific payload hash.

A standardized asynchronous state suspension and cryptographic resumption protocol is necessary to resolve this operational and security impasse.

## Proposal

Adopt the normative specification in [`../spec/0.1/hitl.md`](../spec/0.1/hitl.md). This RFC defines:

1. **`decision: "ask"` Response Contract**:
   When human intervention is required, the security receiver returns `permissionDecision: "ask"` with an `escalation` object containing `challenge_id`, `approval_url`, `timeout_seconds`, and target `channels`.
2. **Turn Suspension**:
   The runtime freezes the active tool invocation turn into `SUSPENDED` state without crashing or canceling the agent context. Remote connections respond with HTTP `202 Accepted` and hold an SSE stream or register a webhook callback.
3. **Multi-Channel Escalation Cards**:
   The Approval Gateway renders contextual approval cards in Slack Block Kit, Microsoft Teams Adaptive Cards, or ServiceNow ITSM tickets containing the initiator identity, target tool, sanitized parameters, and RFC 8785 content hash.
4. **Cryptographic `ApprovalGrantToken`**:
   Upon human approval, the Policy Decision Point mints a cryptographically signed token binding the `session_id`, `tool_use_id`, `content_identity`, approver identity, and a 300-second expiration window.
5. **Deterministic 1-Microsecond Pre-Dispatch TOCTOU Check**:
   Before executing the tool, the runtime verifies in memory that `token.content_identity == compute_jcs_sha256(staged_tool_input)`. If memory or disk was tampered with, execution immediately aborts.

## Compatibility impact

- **Backward Compatibility**: Fully backward-compatible with Agent Hook 0.1. Clients that do not support asynchronous suspension continue to handle `permissionDecision: "ask"` as a synchronous terminal prompt or fallback to fail-open/closed per local policy.
- **Schema Compatibility**: Extends `schemas/hook-response.schema.json` with the optional `escalation` and `approval_grant_token` fields inside `hookSpecificOutput`. Existing valid response fixtures remain 100% valid.

## Security and privacy impact

- **TOCTOU Defense**: Eliminates the memory/disk bait-and-switch vulnerability between human approval and tool dispatch.
- **Dual Custody & Non-Repudiation**: Establishes verifiable proof of human authorization for high-risk operations (e.g. production deployments, financial transactions, IAM grants).
- **Privacy Minimization**: Notification cards delivered to third-party chat platforms (Slack/Teams) SHOULD redact credentials and proprietary source code while displaying the exact cryptographic digest.

## Alternatives considered

- **Synchronous Connection Holding**: Keeping the HTTP request open until a human clicks approve. Rejected due to ubiquitous 30-60s proxy and gateway timeouts.
- **Plaintext Approval Tokens**: Passing an unsigned string ticket (`ticket_id: "123"`). Rejected because any local process could forge resumption tickets without cryptographic origin proof.

## Decision record

- Initiated from community and enterprise requirements for asynchronous human-in-the-loop turn suspension and dual-custody resumption protocols.
- Adopted normative specification in [`../spec/0.1/hitl.md`](../spec/0.1/hitl.md).
- Pending review by maintainers.
