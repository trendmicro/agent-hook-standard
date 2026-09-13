---
sidebar_position: 5
---

# Security considerations

Hook payloads can contain user prompts, filesystem paths, source code, tool
arguments, tool outputs, model requests and responses, environment details, and
credentials. Hosts, adapters, and handlers MUST treat all event data as
untrusted input and SHOULD minimize the values they expose, persist, or
transmit.

## Policy authority

An Agent Hook control response that permits an operation only passes that
handler's gate. It MUST NOT bypass native approval, sandbox, organization,
managed-policy, or platform restrictions. A refusal reason should be useful to
the agent but MUST NOT expose secrets or protected policy details. A response
that requests approval must use a host approval flow; non-interactive hosts MUST
deny instead of assuming consent.

Only the gate events defined by the event registry may interpret a control
response: `UserPromptSubmit`, `BeforeModelRequest`, `PreToolUse`, `PermissionRequest`,
`PreNetworkAccess`, `PreMemoryWrite`, `ConfigChange`, `SessionRevoke`, and when
declared as a gate, `SessionStart` and `SubagentStart`. A host MUST ignore a
control response for any other `hook_event_name` for control purposes. In
particular, a control response returned for an event that reports a completed,
failed, denied, or ended operation MUST NOT be represented as preventive enforcement.

## The Five Enterprise Security Pillars

Implementations conforming to enterprise security profiles SHOULD uphold the
following foundational security pillars:

1. **Zero-Trust Identity & Attestation**:
   Every agent action and delegation chain MUST be attributed to a verifiable
   initiator (`actor.subject`) and bound to runtime cryptographic keys.
2. **Deterministic TOCTOU Defense**:
   All operations evaluated by human or automated policy MUST be cryptographically
   fingerprinted using RFC 8785 (JCS) SHA-256 digests (`content_identity`). Hosts
   MUST re-verify this digest in-memory immediately prior to tool dispatch.
3. **Wire Authentication & Non-Repudiation**:
   Inter-service hook transport MUST enforce request and response signing via
   Ed25519 digital signatures (`Hook-Signature`), coupled with UUIDv7 monotonic
   ordering and replay protection windows.
4. **Kernel-Enforced Perimeter & Network Gating**:
   Agent runtimes MUST NOT rely solely on userland prompt guardrails. Outbound
   network connections MUST be intercepted at `PreNetworkAccess` via OS-level
   sandboxing, proxies, or eBPF to prevent SSRF and internal infrastructure probing.
5. **Tamper-Evident Audit Ledgers (EU AI Act Article 12)**:
   Audit logs MUST be formatted using 4-Block records chained via `prev_record_hash`
   cryptographic digests, guaranteeing legal non-repudiation.

## Handler isolation and transport

Agent Hook does not standardize execution isolation or transport. Hosts SHOULD
run handlers with least privilege, provide only the working-directory and
environment access they require, set finite timeouts, and restrict outbound
network destinations. Adapters SHOULD avoid putting credentials into command
arguments, output, or persisted diagnostics.

## Security telemetry and capability claims

The Core event registry provides a minimum vocabulary for reconstructing an
agent security-relevant lifecycle: session and turn boundaries, user ingress,
model requests and responses, tool execution, permission outcomes, and
subagent delegation. Telemetry consumers MUST retain the exact
`hook_event_name`; they MUST NOT replace it with a vendor-native event name.

A host MAY expose only the Core events it can observe faithfully. A conforming
host MUST publish a per-host capability declaration for every Core
`hook_event_name`, using exactly one of these modes:

| Mode | Meaning |
| --- | --- |
| `gate` | The host emits the event at the defined pre-action boundary and can enforce a control response through a native mechanism. |
| `observe` | The host emits the event faithfully but does not treat a response as control. |
| `partial` | The host exposes a related boundary with a documented difference in timing, payload, or control behavior. |
| `unavailable` | The host cannot emit the event faithfully. |

A host MUST NOT claim `gate` when it cannot prevent the pending operation, or
claim `observe` when it only infers the event from a later side effect. A
capability declaration describes the host's observable and enforceable surface;
it does not override an independent security policy.

Security telemetry SHOULD preserve `session_id`, `model_request_id`,
`tool_use_id`, `permission_request_id`, `operation_id`, and `delegation_id`
when they are present. It SHOULD preserve `parent_agent_id` for delegated work.
These identifiers let a consumer distinguish an operation that was denied
before execution from one that executed and later failed, including when tool
calls or subagents run concurrently.

## Failure and telemetry

The 0.1 default is fail open: an unavailable or malformed handler response
does not become a denial. Hosts SHOULD record a minimal diagnostic with the
event ID, `hook_event_name`, handler identity, and failure class. They SHOULD
redact or omit prompt text, model data, tool data, secrets, and personal data
from those records. A diagnostic record SHOULD retain only the correlation
identifiers and outcome needed to investigate the event.

Handlers SHOULD validate the event schema before producing a security control
response and SHOULD return only one correlated response. A response for a different
event ID is invalid and must fail open under the core protocol.
