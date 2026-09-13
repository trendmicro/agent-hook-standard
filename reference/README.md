# Agent Hook Standard: Reference Implementation & Conformance Suite

This directory contains the normative **Python Reference Implementation and Conformance Test Suite** for the Agent Hook Standard. It demonstrates an end-to-end implementation of both the **Agent Policy Enforcement Point (PEP)** and the **Enterprise Security Policy Decision Point (PDP)** conforming to Agent Hook 0.1 and the **Twelve Cybersecurity Defense Gates**.

---

## Architecture Overview

```
+-------------------------------------------------------------------------------+
|                            REFERENCE ARCHITECTURE                             |
|                                                                               |
|  +-------------------+       HTTP / Wire Protocol       +-------------------+  |
|  |    Agent PEP      |=================================>|   Security PDP    |  |
|  |   (`agent.py`)    |<=================================|  (`receiver.py`)  |  |
|  +-------------------+        (Ed25519 Signed)          +-------------------+  |
|           |                                                       |           |
|     (RFC 8785 JCS)                                           (12 Gates Eval)  |
|           v                                                       v           |
|  +-------------------+                                  +-------------------+  |
|  | TOCTOU Validation |                                  |  4-Block Ledger   |  |
|  |   (1-µs Check)    |                                  |   (`crypto.py`)   |  |
|  +-------------------+                                  +-------------------+  |
|                                                                   |           |
|                                                              (if "ask")       |
|                                                                   v           |
|                                                         +-------------------+  |
|                                                         |    HITL Gateway   |  |
|                                                         |    (`relay.py`)   |  |
|                                                         +-------------------+  |
+-------------------------------------------------------------------------------+
```

---

## Directory Structure

- **`models.py`**: Pydantic / Data models supporting the **Hybrid Flat Schema** (`spec: "agent-hooks/0.1"`, `hook_event_name`, top-level `tool_name` / `tool_input` / `destination_host`, and nested `actor` / `trace` / `escalation`).
- **`crypto.py`**: Cryptographic primitives:
  - **RFC 8785 JSON Canonicalization Scheme (JCS)** for deterministic SHA-256 payload hashing (`content_identity`).
  - **Ed25519** digital signatures for wire transport authentication (`Hook-Signature`).
  - **4-Block Audit Ledger** hash-chaining (`prev_record_hash`).
- **`receiver.py`**: Reference Enterprise Policy Decision Point (PDP) server evaluating the Twelve Cybersecurity Defense Gates.
- **`agent.py`**: Reference Agent Runtime Policy Enforcement Point (PEP) executing tools with 1-microsecond pre-dispatch TOCTOU verification.
- **`relay.py`**: Reference Approval Relay Gateway handling asynchronous turn suspension and Slack/Teams resumption tokens (RFC 0003).
- **`verify_scenarios.py`**: Automated conformance suite testing **22 end-to-end security scenarios covering all Twelve Cybersecurity Defense Gates**.
- **`verify_hitl_scenarios.py`**: Automated test suite for **6 asynchronous HITL and turn resumption scenarios**.

---

## Quick Start: Running the Conformance Suite

### 1. Requirements

- Python >= 3.10
- Install dependencies:

```bash
pip install -r requirements.txt
```

*(Only requires `cryptography>=42.0.0`; all networking and schemas utilize standard library.)*

### 2. Run the 22 Security Defense Gates Scenarios

```bash
python verify_scenarios.py
```

**Validated Scenarios (100% Pass across all 12 Gates)**:
1. `PreToolUse`: Normal Safe Tool Execution (`allow`) [Gate 5]
2. `PreToolUse`: Secret Exfiltration & Malicious Command (`deny` + grant revocation) [Gate 5 / Gate 6]
3. `PreToolUse`: Insecure Command Sanitization (`transform` rewrite) [Gate 5]
4. `PreToolUse`: Privileged Action Escalation (`ask` trigger) [Gate 5]
5. `PreNetworkAccess`: SSRF Cloud Metadata Probing (`169.254.169.254` blocked) [Gate 7]
6. `UserPromptSubmit`: Direct Prompt Injection Detection (`deny`) [Gate 2]
7. `PreToolUse`: Rate Limiting & Autonomous Backoff (`throttle` + retry) [Gate 5]
8. Fail-Closed Timeout Enforcement (`fail_mode: closed` aborts execution)
9. Fail-Open Timeout Fallback (`fail_mode: open` proceeds on timeout)
10. Wire Signature Forgery Detection (HTTP 401 Unauthorized)
11. Anti-Replay Protection (HTTP 409 Conflict)
12. Clock Drift Tolerance Protection (±300s window enforcement)
13. TOCTOU Bait-and-Switch Memory Tamper Detection (immediate execution abort)
14. Control-Plane `SessionRevoke` Kill Switch (instant container lockdown) [Gate 12]
15. 4-Block Tamper-Evident Audit Ledger Validation (`prev_record_hash` chain verification)
16. `SessionStart`: Environment & Host Sandbox Integrity (LD_PRELOAD block) [Gate 1]
17. `BeforeModelRequest`: Model Egress DLP & Secret Leaking Prevention (IAM token block) [Gate 3]
18. `AfterModelResponse`: Hallucinated Destructive Output Guardrail (`rm -rf /` block) [Gate 4]
19. `PostNetworkAccess`: Anomalous Network Exfiltration Telemetry (15MB volume block) [Gate 8]
20. `SubagentStart`: Confused Deputy & Recursive Delegation Defense [Gate 9]
21. `PreMemoryWrite`: Vector Memory Poisoning & Sleeper Agent Defense [Gate 10]
22. `ConfigChange`: MCP & Security Rules Tamper Defense [Gate 11]

### 3. Run the Asynchronous HITL Scenarios

```bash
python verify_hitl_scenarios.py
```

**Validated HITL Scenarios**:
1. Local CLI Terminal Interactive Confirmation
2. Remote Out-of-Band Managerial Approval via Slack
3. TOCTOU Bait-and-Switch Detection during Suspended State
4. Forged Approval Grant Token Rejection
5. Expired Approval Token Fail-Closed Rejection
6. Explicit Human Approver Rejection via Slack
