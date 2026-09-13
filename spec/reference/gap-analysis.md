# Cybersecurity Field Gap Analysis: Twelve Defense Gates

## Executive Summary

To understand *why* the Enterprise Security additions are introduced into Agent Hook 0.1, this reference establishes the baseline of what commercial agent runtimes (Claude Code, OpenAI Codex, Microsoft Agent Hooks, Google Gemini CLI, GitHub Copilot) provide out-of-the-box, what security checks they achieve, and the critical security blind spots they leave completely exposed.

---

## 1. What Current Commercial Agent Runtimes Provide Today

Across mainstream commercial AI agents, hook data contracts are typically limited to local process-level JSON representations:
* **Common Ingress Fields**: `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input` (command string/arguments), `permission_mode`, and `transcript_path`.
* **Common Egress Fields**: `permissionDecision` (`allow` | `deny` | `block`), `updatedInput` (string rewrite), and text reasons.

### Security Checks Achievable with Current Fields:
1. **Static Regex / Command Blacklisting**: Matching `tool_input.command` against `rm -rf /`, `mkfs`, `sudo`, `dd` to reject obvious malicious commands.
2. **Path Traversal Guardrails**: Checking `tool_input.file_path` to block writes outside `cwd` or access to `/etc/passwd`, `~/.ssh/`, `.env`.
3. **Parameter Rewriting / Sanitization**: Rewriting `http://` to `https://` or appending `--dry-run` flags via `updatedInput`.
4. **Synchronous Local Terminal Confirmation**: Pausing console execution to prompt `[y/N]` when `permission_mode` requires manual approval.
5. **Post-Execution Auditing**: Appending completed tool inputs and statuses to local JSONL transcript logs.

---

## 2. The Critical Security Blind Spots (What Current Baseline CANNOT Defend)

Despite the checks above, existing vendor contracts suffer from six fatal architectural vulnerabilities:

1. **Zero TOCTOU Protection**: Vendor runtimes provide no hash digest (`content_identity`). If memory is mutated or a script on disk is swapped during background queueing or human review, the runtime executes the swapped payload blindly.
2. **Zero Wire-Level Authentication & Non-Repudiation**: Requests only have plaintext `session_id` without `actor.subject` or digital signatures (`Hook-Signature`), allowing any local process or rogue proxy to forge hook calls.
3. **Zero Anti-Replay Defense**: Lacks monotonically increasing sequence numbers or clock drift timestamps (`Hook-Timestamp`), enabling attackers to replay past legitimate actions indefinitely.
4. **Zero Root-of-Intent Visibility (Prompt Injection Blindness)**: Hooks only see the immediate `tool_input`. Without root intent context and `thought_process`, security engines cannot detect when an agent has been hijacked via Indirect Prompt Injection (IPI).
5. **Zero Network Egress Gating**: No vendor provides a per-connection `PreNetworkAccess` hook with destination IP/domain visibility before socket creation, leaving systems completely vulnerable to SSRF (e.g. cloud metadata `169.254.169.254`).
6. **Zero Asynchronous Enterprise HITL**: Without `escalation` schemas, approval requires synchronous connection holding, inevitably tripping HTTP/gRPC timeouts for enterprise Slack/ITSM workflows.

---

## 3. Side-by-Side Architectural Gap Matrix

| Security Capability | Current Vendor Baseline (Claude Code, Codex, Gemini) | Enterprise Security Specification (Our Merge) | Required New Fields / Mechanics | Security Risk If Missing |
|---|---|---|---|---|
| **TOCTOU Bait-and-Switch Defense** | ❌ **Unsupported** (Plaintext `tool_input` only; no pre-dispatch check) | ✅ **Enforced** (RFC 8785 SHA-256 + 1µs Pre-Dispatch Check) | `content_identity`, `content_identity_binding`, `approval_grant_token` | Command swapped in memory/disk during review; agent executes hijacked code. |
| **Caller Identity & Wire Auth** | ❌ **Unsupported** (Plaintext `session_id` only; host assumed trusted) | ✅ **Enforced** (Ed25519 asymmetric signatures per request) | `actor.subject`, `actor.assurance_level`, `Hook-Signature` header | Forged hook requests, unauthorized privilege escalation, non-repudiation failure. |
| **Anti-Replay Protection** | ❌ **Unsupported** (No timestamp window, no replay cache) | ✅ **Enforced** (UUIDv7 + 300s clock drift + seen attempt cache) | `Hook-Id`, `Hook-Timestamp`, `sequence` | Replaying legitimate historical approvals (e.g. re-executing funds transfer 10,000 times). |
| **Prompt Injection (IPI) Detection** | ❌ **Blind** (Sees only current `tool_input`; blind to root intent) | ✅ **Context-Aware** (Dual alignment: root prompt vs. tool input) | `thought_process`, `prompt_id` causal turn correlation | Poisoned context tricks agent into issuing malicious commands disguised as normal tasks. |
| **Network Egress / SSRF Defense** | ❌ **Missing** (No socket connection hook; only passive sandbox notice) | ✅ **Kernel-Enforced** (Intercepts destination host/port via eBPF/proxy) | `PreNetworkAccess`, `destination_host`, `destination_port` | Agent connecting to internal metadata `169.254.169.254` or internal microservices. |
| **Asynchronous Multi-Channel HITL** | ❌ **Broken** (Synchronous wait only; connection timeout on Slack wait) | ✅ **Turn Suspension** (Non-blocking SSE / REST 202 + Slack Block Kit) | `permissionDecision: "ask"`, `escalation`, `ApprovalGrantToken` | Network timeout crashes agent turn when human approval takes >2 seconds. |
| **Tamper-Evident Audit Record** | ❌ **Plain Text JSONL** (Easily truncated or altered locally) | ✅ **Hash-Chained Ledger** (Block 1-4 with `prev_record_hash`) | 4-Block schema, Ed25519 signature, `prev_record_hash` | Non-compliance with EU AI Act Article 12; failure of legal evidence admissibility. |
