---
title: "RFC 0002: Enterprise Security Defense Gates, Wire Signatures, and Tamper-Evident Audit Ledger"
status: Draft
discussion: "https://github.com/trendmicro/agent-hook-standard/discussions/TBD-0002"
review-start: TBD
review-end: TBD
maintainer-votes: []
decision: "Pending"
supersedes: []
superseded-by: []
---

# RFC 0002: Enterprise Security Defense Gates, Wire Signatures, and Tamper-Evident Audit Ledger

## Summary

This RFC proposes the **Enterprise Security Defense Gates, Wire Signatures, and Tamper-Evident Audit Ledger** extension for Agent Hook 0.1. It formalizes the **Twelve Cybersecurity Defense Gates** (adding `PreNetworkAccess`, `PostNetworkAccess`, `PreMemoryWrite`, `PostMemoryWrite`, `ConfigChange`, and `SessionRevoke` to the core event registry), mandates **RFC 8785 JSON Canonicalization (JCS)** for cryptographic content identity, specifies transport wire security headers (`Hook-Id`, `Hook-Timestamp`, `Hook-Attempt`, `Hook-Signature`, `Hook-Response-Signature`), and introduces the **4-Block Tamper-Evident Audit Record** with cryptographic hash chaining (`prev_record_hash`) satisfying EU AI Act Article 12 non-repudiation requirements.

## Motivation

Standard commercial agent hook facilities were designed for local developer workflows. When deployed in enterprise environments, autonomous agents interact directly with file systems, internal microservices, and persistent memories. Current baseline specifications leave severe security blind spots:
1. **SSRF & Data Exfiltration**: Agents can initiate outbound socket connections to cloud metadata (`169.254.169.254`) or internal databases without an egress interception point.
2. **Memory Poisoning**: Agents persisting unvetted tool output into vector databases can embed cross-session sleeper instructions.
3. **Supply-Chain & Configuration Tampering**: Compromised agents can silently rewrite `.agents/rules`, `settings.json`, or register rogue MCP servers.
4. **Wire Forgery & Replay**: Plaintext JSON transport allows rogue proxies or local processes to forge `allow` decisions or replay historical approvals.
5. **Auditing Vulnerabilities**: Plaintext JSONL logs can be truncated or modified after an incident, failing legal evidence standards.

## Proposal

Adopt the normative specifications in [`../spec/0.1/events.md`](../spec/0.1/events.md), [`../spec/0.1/core.md`](../spec/0.1/core.md), [`../spec/0.1/security.md`](../spec/0.1/security.md), and [`../spec/0.1/audit-ledger.md`](../spec/0.1/audit-ledger.md).

### 1. Twelve Cybersecurity Defense Gates
Promote the following boundaries into the Core event registry:
- **`PreNetworkAccess` & `PostNetworkAccess`**: Kernel/socket-level egress interception for SSRF and C2 defense.
- **`PreMemoryWrite` & `PostMemoryWrite`**: Gating persistence into long-term stores to prevent memory poisoning.
- **`ConfigChange`**: Gating modifications to configuration, MCP manifests, and rule files.
- **`SessionRevoke`**: Out-of-band kill-switch from enterprise SOC/SIEM to isolate and terminate compromised sessions.
- Upgrade `SessionStart` (Gate 1) and `SubagentStart` (Gate 9) to support `Gate` classification.

### 2. RFC 8785 JSON Canonicalization Scheme (JCS)
Mandate that all payload fingerprints (`content_identity`) and audit hashes MUST be computed over the RFC 8785 canonical bytes of the JSON payload, eliminating whitespace, key-ordering, and unicode encoding drift across multi-language runtimes.

### 3. Transport Security Headers
Standardize HTTP/transport wire headers:
- `Hook-Id`: UUIDv7 anti-replay identifier.
- `Hook-Timestamp`: RFC 3339 UTC timestamp with 300s window.
- `Hook-Attempt`: Monotonically increasing attempt counter.
- `Hook-Signature`: Ed25519 signature computed over `"{Hook-Id}.{Hook-Timestamp}.{Hook-Attempt}.{CanonicalBody}"`.
- `Hook-Response-Signature`: Receiver signature for mutual authentication.

### 4. 4-Block Tamper-Evident Audit Ledger
Standardize the audit record structure into:
- **Block 1**: Agent & Host Provenance Context.
- **Block 2**: Payload Content & RFC 8785 Fingerprint.
- **Block 3**: Local Enforcement Decision.
- **Block 4**: Security Enrichment & Cryptographic Chaining (`prev_record_hash`, `record_hash`, Ed25519 signature).

## Compatibility impact

- **Envelope Stability**: Retains the flat Claude Code-shaped request envelope (`spec: "agent-hooks/0.1"`). Enterprise security metadata (`actor`, `delegation_chain`, `content_identity`, `thought_process`) are optional flat top-level members.
- **Fail-Open Default Preserved**: General workstation implementations continue to fail-open. The Enterprise Zero-Trust Profile permits explicit configuration of `fail_mode: "closed"` on critical defense gates.

## Security and privacy impact

- Provides end-to-end zero-trust perimeter defense against SSRF, memory poisoning, configuration hijacking, and indirect prompt injection.
- Guarantees non-repudiation and tamper detection for legal compliance and post-incident forensic investigation.

## Alternatives considered

- **Per-Tool Network Gating**: Treating network access as ordinary tool calls (`fetch`). Rejected because tools like `Bash` or native python scripts can open raw sockets bypassing tool-level hooks; network gating requires socket/proxy/eBPF interception at `PreNetworkAccess`.
- **Ad-hoc JSON Hashes**: Standard SHA-256 over serialized strings without JCS. Rejected because cross-language runtimes produce mismatched hashes due to whitespace and key sorting.

## Decision record

- Initiated from community and enterprise requirements for the Twelve Cybersecurity Defense Gates, kernel network gating, and tamper-evident audit ledger hash-chaining.
- Adopted normative specifications in [`../spec/0.1/events.md`](../spec/0.1/events.md), [`../spec/0.1/security.md`](../spec/0.1/security.md), and [`../spec/0.1/audit-ledger.md`](../spec/0.1/audit-ledger.md).
- Pending review by maintainers.
