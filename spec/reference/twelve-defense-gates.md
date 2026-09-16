# Twelve Cybersecurity Defense Gates: Data Contracts & Threat Models

## Overview

The **Twelve Cybersecurity Defense Gates** constitute the core perimeter defense model for autonomous AI agents. Unlike non-security lifecycle notifications, these gates are fail-closed decision points (when running under an Enterprise Zero-Trust Profile) where runtime intervention occurs *before* irreversible actions take effect.

```
+----------------------------------------------------------------------------------------------------+
|                               THE TWELVE CYBERSECURITY DEFENSE GATES                               |
+------------------------------------+---------------------------------------------------------------+
| Ingress & Planning Perimeter       | 1. SessionStart (Environment Sanitization)                    |
|                                    | 2. UserPromptSubmit (Prompt Injection & Jailbreak Defense)   |
|                                    | 3. BeforeModelRequest / PreModelCall (Egress DLP & Guardrails)|
|                                    | 4. AfterModelResponse / PostModelCall (Hallucination Defense) |
+------------------------------------+---------------------------------------------------------------+
| Tool & System Execution Perimeter  | 5. PreToolUse (TOCTOU Defense & Asynchronous HITL Trigger)    |
|                                    | 6. PostToolUse (Output Tamper Detection & Result DLP)         |
|                                    | 7. PreNetworkAccess (Kernel-Enforced SSRF & C2 Gating)        |
|                                    | 8. PostNetworkAccess (Traffic Volume & Egress Audit)          |
+------------------------------------+---------------------------------------------------------------+
| Multi-Agent, Memory & Control Plane| 9. SubagentStart / PreAgentCall (Confused Deputy Prevention)  |
|                                    | 10. PreMemoryWrite (Vector & Long-Term Memory Poisoning)      |
|                                    | 11. ConfigChange (MCP & Configuration Tamper Defense)         |
|                                    | 12. SessionRevoke (Out-of-Band Emergency Kill-Switch)         |
+------------------------------------+---------------------------------------------------------------+
```

---

## Gate-by-Gate Specification

### Gate 1: `SessionStart` (Environment & Sandbox Integrity)
* **Lifecycle Boundary**: Fired before any execution begins in a session context.
* **Threat Model**: Host container breakout, `LD_PRELOAD` library injection, malicious `HTTP_PROXY` redirects, and unauthenticated tenant escalation.
* **Input Fields**: `source`, `cwd`, `environment_vars`, `host_fingerprint`, `actor`, `idp_token_claims`.
* **Decision Response**: `allow` (permit start), `deny` (abort session), `transform` (sanitize environment variables).

### Gate 2: `UserPromptSubmit` (Prompt Injection & Ingress Guard)
* **Lifecycle Boundary**: Fired when an external user prompt is received, before agent planning.
* **Threat Model**: Direct prompt injection, system prompt leakage attacks, jailbreak attempts, and ingress secret pasting.
* **Input Fields**: `prompt`, `prompt_id`, `actor`.
* **Decision Response**: `decision: "block"` with `reason`.

### Gate 3: `BeforeModelRequest` / `PreModelCall` (Model Egress DLP)
* **Lifecycle Boundary**: Fired immediately before prompt dispatch to the LLM inference provider.
* **Threat Model**: Data exfiltration of proprietary codebase, API tokens, or PII into public LLM model context.
* **Input Fields**: `prompt_id`, `model_request_id`, `model`, `messages`.
* **Decision Response**: `allow`, `deny`, or `updatedMessages` (scrubbed and tokenized messages).

### Gate 4: `AfterModelResponse` / `PostModelCall` (Output Guardrail & Hallucination)
* **Lifecycle Boundary**: Fired upon completion of model inference.
* **Threat Model**: Model generating malicious payloads, hallucinated destructive commands, or insecure code snippets.
* **Input Fields**: `prompt_id`, `model_request_id`, `model`, `outcome`, `response`, `error`.
* **Decision Response**: Observational audit with output security classification.

### Gate 5: `PreToolUse` (TOCTOU Defense & Asynchronous HITL)
* **Lifecycle Boundary**: Fired before any tool execution begins.
* **Threat Model**: Unauthorized tool execution, malicious argument injection, memory mutation between review and dispatch (TOCTOU).
* **Input Fields**: `prompt_id`, `tool_name`, `tool_input`, `tool_use_id`, `content_identity` (RFC 8785 SHA-256), `thought_process`.
* **Decision Response**: `allow`, `deny`, `updatedInput`, or `ask` (with `escalation` card for Slack/Teams approval).

### Gate 6: `PostToolUse` (Tool Output Integrity & Result DLP)
* **Lifecycle Boundary**: Fired immediately after tool execution completes.
* **Threat Model**: Tool returning poisoned output containing Indirect Prompt Injection (IPI) designed to hijack subsequent model turns.
* **Input Fields**: `prompt_id`, `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `duration_ms`.
* **Decision Response**: Audit record generation, output sanitization.

### Gate 7: `PreNetworkAccess` (SSRF & Perimeter Egress Defense)
* **Lifecycle Boundary**: Fired before opening outbound TCP/UDP network sockets.
* **Threat Model**: Server-Side Request Forgery (SSRF) hitting cloud metadata `169.254.169.254`, internal database probing (RFC 1918), C2 communication.
* **Input Fields**: `prompt_id`, `destination_host`, `destination_port`, `protocol`, `tls_fingerprint`.
* **Decision Response**: `allow` or `deny`.

### Gate 8: `PostNetworkAccess` (Network Volume & Exfiltration Telemetry)
* **Lifecycle Boundary**: Fired upon socket closure.
* **Threat Model**: Slow-and-low data exfiltration, abnormal byte volume leaks.
* **Input Fields**: `prompt_id`, `destination_host`, `destination_port`, `bytes_sent`, `bytes_recv`, `status_code`.

### Gate 9: `SubagentStart` / `PreAgentCall` (Confused Deputy & Attenuation)
* **Lifecycle Boundary**: Fired before child agent process or delegation begins.
* **Threat Model**: Confused Deputy attacks where a low-privilege subagent executes high-privilege operations, runaway recursive agent forks.
* **Input Fields**: `prompt_id`, `delegation_id`, `agent_id`, `agent_type`, `parent_agent_id`, `delegation_chain`.
* **Decision Response**: `allow`, `deny`, or capability attenuation.

### Gate 10: `PreMemoryWrite` (Memory Poisoning & Sleeper Agents)
* **Lifecycle Boundary**: Fired before committing state or embeddings to persistent vector memory.
* **Threat Model**: Cross-session persistent prompt injection, poisoning shared agent knowledge bases.
* **Input Fields**: `prompt_id`, `memory_store_id`, `memory_key`, `content`, `content_identity`.
* **Decision Response**: `allow`, `deny`, or `updatedContent`.

### Gate 11: `ConfigChange` (Configuration & Supply Chain Tamper Defense)
* **Lifecycle Boundary**: Fired before modifying configuration or rule files on disk.
* **Threat Model**: Malicious agent altering `.agents/rules`, modifying `settings.json`, or registering rogue MCP servers to bypass security hooks.
* **Input Fields**: `config_file_path`, `mutation_type`, `old_value_hash`, `new_value_hash`.
* **Decision Response**: `allow` or `deny` (reverts file write).

### Gate 12: `SessionRevoke` (Out-of-Band Incident Containment Kill-Switch)
* **Lifecycle Boundary**: Triggered out-of-band by enterprise SIEM/SOC or runtime watchdog.
* **Threat Model**: Active security incident where an agent has been compromised and must be immediately halted.
* **Input Fields**: `revoke_reason`, `revoked_by`.
* **Effect**: Hard kill-switch; immediate process termination, container network isolation, and ephemeral credential wipe.
