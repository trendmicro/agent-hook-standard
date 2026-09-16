---
title: "RFC 0006: Enterprise Security Extensions Strategy & Non-Core Capabilities"
status: Draft
discussion: "Pending — repository Discussions are not enabled"
review-start: "Not started"
review-end: "Not scheduled"
maintainer-votes: []
decision: "Pending"
supersedes: []
superseded-by: []
---

# RFC 0006: Enterprise Security Extensions Strategy & Non-Core Capabilities

## Summary

This RFC proposes a standardized architectural strategy and recommended extension profiles for enterprise-grade security capabilities within the Agent Hook ecosystem.

To preserve the minimalism, zero-dependency, and lightweight nature of the **Agent Hook Core 0.1 Specification**, heavy enterprise defense features—such as cryptographic wire signing (Ed25519/TPM), tamper-evident audit ledgers (hash-chaining), asynchronous Human-in-the-Loop (HITL) suspension, Time-of-Check to Time-of-Use (TOCTOU) payload verification, and out-of-band administrative session revocation—are explicitly designated as **optional, non-core extension profiles**.

These profiles leverage the existing standard `extensions` container defined in [`spec/0.1/extensions.md`](../spec/0.1/extensions.md). Conforming implementations are free to adopt, customize, or omit these extensions without breaking Core 0.1 interoperability.

---

## Motivation

### The Architectural Dilemma

When designing runtime security governance standards for autonomous AI agents, two distinct sets of requirements emerge:

1. **Open Source & Lightweight Developers (OSS / Consumer Agents)**:
   - Demand zero heavy dependencies, minimal overhead, and absolute ease of adoption.
   - A single-file Python script or simple TypeScript agent should run without needing C cryptography bindings, hardware TPM drivers, or asynchronous webhook suspension queues.
2. **Enterprise, FinTech, & Regulated Sectors (Enterprise / GovTech / SEC Compliance)**:
   - Demand non-repudiation, tamper-evident audit trails for forensic admissibility, cryptographic hardware identity, asynchronous human approval across corporate chat tools (Slack/Teams), and immediate administrative kill-switches.

Forcing heavy enterprise armor into the **Core 0.1 normative specification** would alienate open-source developers and slow down adoption. Conversely, providing no standard for enterprise capabilities leads to fragmentation, proprietary vendor lock-in, and incompatible custom forks.

### Guiding Philosophy

> **"Core does subtraction (protecting a universal minimal baseline); Extensions do addition (mounting modular enterprise armor on demand)."**

By establishing a standardized yet strictly optional **Enterprise Security Extension Profile**, this RFC provides a common blueprint for high-security implementations (such as PEP proxies like NVIDIA NeMo Guardrails/Relay and Policy Decision Points like Trend Micro Vision One) while guaranteeing 100% interoperability with lightweight Core 0.1 agents.

---

## Proposal

### 1. Scope & Core vs. Non-Core Boundary

The following capabilities are classified as **Tier 2 (Enterprise Extension Profiles)** and **Tier 3 (Control-Plane Operations)**:

```
+---------------------------------------------------------------------------------------------------+
|                        Agent Hook Security Governance Hierarchy                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ TIER 1: Core 0.1 Protocol ] (Normative Baseline)                                              |
|  - Flat JSON Envelopes, Top-Level Decision & Reason, 18 Core Lifecycle Events                     |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ TIER 2: Enterprise Extension Profiles ] (Optional Profiles via extensions[...])               |
|                                                                                                   |
|   1. Zero-Trust Wire Signing    2. Tamper-Evident Ledger     3. Asynchronous HITL   4. TOCTOU Guard |
|      (sec.enterprise.crypto)      (sec.enterprise.audit)      (sec.enterprise.hitl)  (sec.enterprise.integrity) |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ TIER 3: Control-Plane Management ] (Out-of-band Administrative Channel)                         |
|                                                                                                   |
|   5. Emergency Administrative Kill Switch (x-nemo/SessionRevoke or POST /sessions/{id}/revoke)    |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

#### Gap Analysis of Non-Core Capabilities

| Capability | Primary Value | Why Kept Out of Core 0.1 | Recommended Disposition |
| :--- | :--- | :--- | :--- |
| **1. Cryptographic Wire Signing** | Hardware-grade authenticity (Ed25519/TPM); prevents spoofed agent events. | Requires crypto dependencies (`cryptography`, libsodium) and key management infrastructure. | Optional profile under `extensions["sec.enterprise.crypto"]` or HTTP header `Hook-Signature`. |
| **2. Tamper-Evident Audit Ledger** | Hash-chained records (`prev_record_hash`) providing forensic non-repudiation. | Imposes sequencing and storage overhead unsuitable for stateless lambdas/microservices. | Optional profile under `extensions["sec.enterprise.audit"]`. |
| **3. Asynchronous HITL Suspension** | Async suspension with signed resumption tokens (`ApprovalGrantToken`) via Slack/Teams. | Involves long-lived state queues and callback channels beyond Core synchronous request/response. | Optional profile under `extensions["sec.enterprise.hitl"]`. |
| **4. TOCTOU Integrity Verification** | Compares payload hash between approval time and execution time. | Application-level invariant check rather than lifecycle dispatch primitive. | Optional profile under `extensions["sec.enterprise.integrity"]`. |
| **5. Emergency Session Revocation** | Out-of-band administrative command to immediately sever agent network & revoke grants. | Control-plane operation, fundamentally distinct from inside-out agent data-plane lifecycle events. | Out-of-band control endpoint (`POST /sessions/{id}/revoke`) or namespaced event `x-nemo/SessionRevoke`. |

---

### 2. Normative Rules for Extensions

All extensions proposed in this RFC adhere strictly to [`spec/0.1/extensions.md`](../spec/0.1/extensions.md):

1. **Non-Mandatory (Opt-In)**: No agent, PEP, or PDP is required to implement any extension defined herein to claim Core 0.1 compliance.
2. **Safe to Ignore**: A consumer that does not understand an extension namespace MUST ignore it without failing validation.
3. **Namespace Autonomy & Customization**:
   - The namespaces defined in this document (e.g., `sec.enterprise.*` or reverse-DNS `com.trendmicro.security.*`) represent **recommended public profiles**.
   - Conforming to Core 0.1 `spec/0.1/extensions.md`, property names under `extensions` MUST be reverse-DNS namespaces using dot notation (`^(?:[a-z][a-z0-9-]*\.)+[a-z][a-z0-9-]*$`).
   - Implementers are free to define proprietary namespaces (e.g., `com.mycompany.security.crypto`) or customize property keys according to their internal architecture.
4. **Parameterized & Open Algorithms**:
   - Cryptographic and hashing algorithms specified in example payloads are **parameterized**. Implementers MAY choose alternative algorithms (e.g., `rsa-pss`, `ecdsa-p256`, post-quantum algorithms like `dilithium`, or alternative hashes like `blake3` and `sha3-512`).

---

### 3. Recommended Profile Specifications

#### 3.1 Profile: Cryptographic Wire Signing (`sec.enterprise.crypto`)

Used to guarantee message authenticity and provenance between Agent, PEP (Relay), and PDP.

##### Request / Response Example
```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "01J8ABCDEF1234567890abcdef",
  "hook_event_name": "PreToolUse",
  "session_id": "sess_production_9981",
  "timestamp": "2026-09-17T02:30:00Z",
  "tool_name": "bash",
  "tool_input": {
    "command": "uname -a"
  },
  "extensions": {
    "sec.enterprise.crypto": {
      "key_id": "key_enclave_prod_01",
      "algorithm": "ed25519",
      "canonical_algorithm": "RFC8785_JCS",
      "canonical_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
      "signature": "MEQCIE...base64_encoded_signature..."
    }
  }
}
```

* **`key_id`** *(string, required)*: Identifier of the public key registered in the enterprise directory.
* **`algorithm`** *(string, optional, default: `"ed25519"`)*: Cryptographic signing algorithm. Implementations MAY specify `"rsa-pss"`, `"ecdsa-p256"`, or post-quantum variants.
* **`canonical_algorithm`** *(string, optional, default: `"RFC8785_JCS"`)*: Canonicalization method used before hashing.
* **`canonical_hash`** *(string, required)*: Hex-encoded digest (`<hash_algo>:<hex>`).
* **`signature`** *(string, required)*: Base64-encoded signature over the canonical hash.

Alternatively, transport-level implementations MAY transport this metadata via HTTP header:
```http
Hook-Signature: key_id="key_enclave_prod_01", alg="ed25519", sig="MEQCIE..."
```

---

#### 3.2 Profile: Tamper-Evident Audit Ledger (`sec.enterprise.audit`)

Enables forensic verification of agent operation history using back-linked hash chains.

##### Example Payload
```json
{
  "extensions": {
    "sec.enterprise.audit": {
      "sequence": 42,
      "prev_record_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
      "record_hash": "f8e7d6c5b4a3928170efdcba9876543210fedcba0987654321abcdef01234567",
      "hash_algorithm": "sha256",
      "tamper_evident_status": "verified"
    }
  }
}
```

* **`sequence`** *(integer, required)*: Monotonically increasing event sequence index for the session.
* **`prev_record_hash`** *(string, required)*: Hex-encoded hash of the previous ledger record (or genesis seed string for `sequence: 0`).
* **`record_hash`** *(string, required)*: Hex-encoded hash of the current record including `prev_record_hash`.
* **`hash_algorithm`** *(string, optional, default: `"sha256"`)*: Hash algorithm used (`"sha256"`, `"sha3-512"`, `"blake3"`).
* **`tamper_evident_status`** *(string, optional)*: State evaluation by the verification point (`"verified"`, `"broken_chain"`, `"unverified"`).

---

#### 3.3 Profile: Asynchronous HITL Suspension (`sec.enterprise.hitl`)

Standardizes asynchronous human intervention when a Policy Decision Point returns `decision: "ask"`.

##### PDP Response with Suspension Challenge
```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "01J8ABCDEF1234567891abcdef",
  "decision": "ask",
  "reason": "Execution of bash shell with root privilege requires administrator sign-off.",
  "extensions": {
    "sec.enterprise.hitl": {
      "mode": "async_suspended",
      "challenge_id": "ch_slack_prod_99182",
      "resumption_channel": "slack://security-operations",
      "expires_at": 1773729900,
      "escalation_policy": "require_manager_approval"
    }
  }
}
```

##### Resumption Callback Request (Triggered by Slack/Teams Approval)
When approved by an authorized administrator, the enterprise PDP or callback service invokes the PEP resumption endpoint with an authorized grant token:
```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "01J8ABCDEF1234567892abcdef",
  "decision": "allow",
  "reason": "Approved by security administrator Alice.",
  "extensions": {
    "sec.enterprise.hitl": {
      "challenge_id": "ch_slack_prod_99182",
      "approval_grant_token": "agt_eyJhbGciOiJFZERTQ...",
      "approved_by": "alice.security.lead@example.com",
      "approved_at": 1773726500,
      "bound_tool_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  }
}
```

* **`mode`** *(string, optional)*: `"sync_prompt"` (synchronous user prompt) or `"async_suspended"` (long-lived asynchronous suspension).
* **`challenge_id`** *(string, required)*: Unique identifier for the human approval challenge.
* **`approval_grant_token`** *(string, optional)*: Cryptographically signed single-use grant token.
* **`expires_at`** *(integer, optional)*: Unix epoch timestamp indicating expiration of the approval challenge.

---

#### 3.4 Profile: TOCTOU Content Fingerprint (`sec.enterprise.integrity`)

Defends against Time-of-Check to Time-of-Use (TOCTOU) payload swapping attacks between policy verification and tool execution.

##### Example Payload
```json
{
  "extensions": {
    "sec.enterprise.integrity": {
      "content_identity": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "enforce_toctou_pre_dispatch": true
    }
  }
}
```

* **`content_identity`** *(string, required)*: Cryptographic hash of the serialized tool input arguments (`tool_input`).
* **`enforce_toctou_pre_dispatch`** *(boolean, optional, default: `true`)*: Instructs the PEP/host to verify that the executed parameters match `content_identity` identically prior to invocation.

---

### 4. Control-Plane Operation: SessionRevoke Emergency Kill Switch

#### Distinction between Data Plane and Control Plane

* **Data-Plane Lifecycle Events** ([`events.md`](../spec/0.1/events.md)): Fired inside-out by the Agent runtime as it progresses (e.g., `PreToolUse`, `AfterModelResponse`).
* **Control-Plane Management Commands**: Fired outside-in by administrative systems or SOC platforms to instruct the PEP/host to terminate execution immediately.

#### Recommended Implementation Formats

Implementations MAY support administrative revocation through either:

1. **REST Management Endpoint**:
   ```http
   POST /v1/sessions/{session_id}/revoke HTTP/1.1
   Host: relay.enterprise.local
   Authorization: Bearer <admin_token>
   Content-Type: application/json

   {
     "reason": "Compromised credentials detected on host machine.",
     "revoked_by": "soc_incident_responder_42",
     "terminate_subagents": true
   }
   ```
2. **Namespaced Extension Event**:
   On internal event buses, implementations MAY emit an extension event adhering to `spec/0.1/events.md`:
   ```json
   {
     "spec": "agent-hooks/0.1",
     "event_id": "01J8ABCDEF1234567893abcdef",
     "hook_event_name": "x-nemo/SessionRevoke",
     "session_id": "sess_production_9981",
     "timestamp": "2026-09-17T02:35:00Z",
     "extensions": {
       "sec.enterprise.control": {
         "action": "terminate",
         "reason": "Administrative kill-switch invoked by SOC"
       }
     }
   }
   ```

Upon receiving a valid revocation command, the PEP/Host MUST:
- Invalidate all active tokens and standing authorizations associated with `session_id`.
- Terminate or cleanly interrupt running subagents and child tasks.
- Sever external network egress proxy connections for the session.
- Append a terminal record to the audit ledger.

---

## Roles & Responsibilities

```
+----------------+      Core 0.1 Events        +-------------------+     Enriched Extensions    +----------------------+
| AI Agent Host  | ──────────────────────────> |  NeMo Relay (PEP) | ─────────────────────────> | Security PDP (Trend) |
| (Lightweight)  | <────────────────────────── |  (Security Proxy) | <───────────────────────── | (Policy Engine)      |
+----------------+       Standard Allow/Deny   +-------------------+    UniversalDecision       +----------------------+
                                                         │                                                 │
                                                         │ Asynchronous Suspension (202)                   │ Slack/Teams
                                                         ▼                                                 ▼
                                                [ Suspension Store ]                              [ Corporate HITL ]
```

1. **AI Agent Host (Lightweight)**:
   - Needs only Core 0.1 compliance.
   - Emits standard lifecycle events.
   - Transparently retains `extensions` without modifying or stripping unrecognized fields.
2. **NeMo Relay / Interceptor Proxy (PEP)**:
   - Bridges the lightweight Agent with heavy enterprise infrastructure.
   - Offloads cryptographic signing, hash-chain ledger maintenance, and connection suspension from the Agent runtime.
   - Enforces TOCTOU verification before dispatching tool executions.
3. **Security Vendor / PDP (e.g., Trend Micro Vision One)**:
   - Evaluates incoming events against enterprise threat intelligence and security policies.
   - Verifies wire signatures and ledger continuity.
   - Returns top-level `decision: "ask"` and issues signed `ApprovalGrantToken` upon human authorization.
   - Issues out-of-band `SessionRevoke` commands when high-severity incidents are detected.

---

## Compatibility Impact

- **Core 0.1 Compatibility**: **100% Compatible**. All mechanisms defined in this RFC reside inside the `extensions` dictionary or out-of-band endpoints. No Core schema fields or mandatory behaviors are altered.
- **Backward Compatibility**: Existing agents that do not understand these extensions continue to function normally. Gate decisions (`allow`, `deny`, `ask`, `defer`) remain in their canonical top-level format.

---

## Security and Privacy Impact

- **Enhanced Integrity**: Cryptographic wire signing and TOCTOU protection prevent adversarial injection and man-in-the-middle tampering.
- **Legal Non-Repudiation**: Hash-chained ledgers provide tamper-evident records suitable for enterprise compliance audits (SOC 2, ISO 27001, GDPR).
- **Privacy Considerations**: Extension payloads (such as audit hashes) SHOULD hash rather than log raw sensitive parameters (PII/secrets) unless explicitly intended for encrypted secure audit vaults.

---

## Alternatives Considered

1. **Mandating signing and hash chains in Core 0.1**: Rejected. Would impose C-extension dependencies and high storage overhead on open-source, CLI, and resource-constrained agents.
2. **Using proprietary vendor protocols outside Agent Hook**: Rejected. Would fragment the ecosystem and force enterprise agents into disparate non-interoperable silos.
3. **Encoding non-core decisions inside `hookSpecificOutput`**: Rejected. Top-level `decision` and `reason` cleanly separate the control plane from data mutations, keeping extensions strictly focused on auxiliary governance metadata.

---

## Appendix: Reference JSON Schemas for Extension Profiles

The following JSON Schemas illustrate how implementations may validate extension payloads independently of the core specification.

### A.1 Wire Signing Profile (`sec.enterprise.crypto`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EnterpriseCryptoExtension",
  "type": "object",
  "properties": {
    "key_id": { "type": "string" },
    "algorithm": { "type": "string", "default": "ed25519" },
    "canonical_algorithm": { "type": "string", "default": "RFC8785_JCS" },
    "canonical_hash": { "type": "string", "pattern": "^[a-z0-9-]+:[a-f0-9]+$" },
    "signature": { "type": "string" }
  },
  "required": ["key_id", "canonical_hash", "signature"],
  "additionalProperties": true
}
```

### A.2 Audit Ledger Profile (`sec.enterprise.audit`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EnterpriseAuditExtension",
  "type": "object",
  "properties": {
    "sequence": { "type": "integer", "minimum": 0 },
    "prev_record_hash": { "type": "string" },
    "record_hash": { "type": "string" },
    "hash_algorithm": { "type": "string", "default": "sha256" },
    "tamper_evident_status": { "type": "string", "enum": ["verified", "broken_chain", "unverified"] }
  },
  "required": ["sequence", "prev_record_hash", "record_hash"],
  "additionalProperties": true
}
```

### A.3 Asynchronous HITL Profile (`sec.enterprise.hitl`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EnterpriseHitlExtension",
  "type": "object",
  "properties": {
    "mode": { "type": "string", "enum": ["sync_prompt", "async_suspended"] },
    "challenge_id": { "type": "string" },
    "approval_grant_token": { "type": "string" },
    "resumption_channel": { "type": "string" },
    "expires_at": { "type": "integer" },
    "approved_by": { "type": "string" },
    "approved_at": { "type": "integer" },
    "bound_tool_hash": { "type": "string" }
  },
  "required": ["challenge_id"],
  "additionalProperties": true
}
```

---

## References

- [RFC 0001: Agent Hook 0.1 Core Event Contract](./0001-agent-hook-core-event-contract.md).
- [RFC 0004: Standard network, memory, and configuration lifecycle events](./0004-standard-lifecycle-events.md).
- [RFC 0005: Inspect and control response content with PostNetworkAccess](./0005-network-response-delivery-inspection.md).
- [Core protocol](../spec/0.1/core.md).
- [Event registry](../spec/0.1/events.md).
- [Extension policy](../spec/0.1/extensions.md).
- [Security considerations](../spec/0.1/security.md).

---

## Decision record

Pending. The prerequisite Discussion, public review window, and formal maintainer votes remain outstanding under repository governance. Core 0.1 remains the normative baseline.
