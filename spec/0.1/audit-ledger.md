---
sidebar_position: 6
---

# Tamper-Evident Audit Ledger Specification

## Status and Purpose

This document defines the normative specification for **Tamper-Evident Audit Records and Cryptographic Ledger Chaining** in Agent Hook 0.1. It satisfies EU AI Act Article 12 compliance (mandatory automated record-keeping throughout the AI lifecycle) and establishes legal non-repudiation for autonomous enterprise agent actions.

## 4-Block Audit Record Architecture

To decouple local synchronous audit emission from heavy cloud security analysis, every auditable hook event is structured into four distinct logical blocks:

```
+-------------------------------------------------------------------------------+
|                        Standard Audit Record Structure                        |
+-------------------------------------------------------------------------------+
| Block 1: Agent & Host Provenance Context                                      |
| - session_id, event_id, sequence, prompt_id, actor.subject, agent_id, cwd     |
+-------------------------------------------------------------------------------+
| Block 2: Payload Content & Cryptographic Fingerprint                          |
| - hook_event_name, tool_name/operation, RFC 8785 content_identity (SHA-256)   |
+-------------------------------------------------------------------------------+
| Block 3: Local PEP Enforcement Verdict                                        |
| - local_decision (allow/deny/ask), evaluated_at, latency_ms                   |
+-------------------------------------------------------------------------------+
| Block 4: Security Enrichment & Cryptographic Chaining                         |
| - receiver_id, policy_evaluations, threat_score, prev_record_hash, signature   |
+-------------------------------------------------------------------------------+
```

### Block 1: Agent & Host Provenance Context
Captures the immutable execution origin of the agent:
- `event_id`: UUIDv7 identifier.
- `session_id`: Unique host session identifier.
- `sequence`: Strictly increasing 64-bit integer within the session.
- `prompt_id`: Causally correlated turn identifier.
- `timestamp`: RFC 3339 UTC timestamp.
- `actor`: Initiator identity (`subject`, `assurance_level`, `tenant_id`).
- `agent_id`: Identifier of the executing agent or subagent.

### Block 2: Payload Content & Cryptographic Fingerprint
Captures the exact intent and parameters of the requested operation:
- `hook_event_name`: Exact Core event name.
- `tool_name` / `destination_host` / `memory_key`: The target resource identifier.
- `content_identity`: Cryptographic SHA-256 fingerprint formatted as `sha256:<hex>`, computed strictly over the **RFC 8785 (JCS)** canonical bytes of the target payload.

### Block 3: Local PEP Enforcement Verdict
Captures the decision rendered prior to execution:
- `decision`: Final verdict applied (`allow`, `deny`, `block`, `transform`).
- `decision_by`: Actor or policy component rendering the verdict.
- `duration_ms`: Latency incurred during hook evaluation.

### Block 4: Security Enrichment & Cryptographic Chaining
Enriches the log with centralized threat intelligence and cryptographic tamper evidence:
- `receiver_id`: Identifier of the Security PDP.
- `policy_rules`: Array of security rules evaluated against the payload.
- `prev_record_hash`: SHA-256 hash of the preceding audit record in the session chain (`"0000...0000"` for session genesis record).
- `record_hash`: SHA-256 digest computed over `sha256(Block1 || Block2 || Block3 || prev_record_hash)`.
- `signature`: Ed25519 digital signature over `record_hash` using the host or security receiver's private key.

## Hash-Chained Non-Repudiation

Within any agent session, every audit record references its immediate predecessor via `prev_record_hash`.
Attempting to delete, insert, or retrospectively alter any past tool invocation or model prompt breaks the cryptographic hash chain, allowing enterprise SIEM/SOC platforms to immediately detect data tampering or log excision.
