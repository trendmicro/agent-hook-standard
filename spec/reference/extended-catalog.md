# Extended Lifecycle Catalog: 39 Canonical Hook Points Across 10 Domains

## Overview

This catalog provides the complete reference taxonomy of **39 canonical hook points across 10 execution domains**, synthesized from real-world implementations across Anthropic Claude Code, OpenAI Codex, Microsoft Agent Hooks, Google Gemini CLI, and GitHub Copilot.

While the Core Agent Hook specification focuses on the **Twelve Critical Cybersecurity Defense Gates (🔴)**, this document details the broader operational, multi-agent, workspace, and developer workflow hooks (⚪) available for advanced orchestration, CI/CD pipelines, and IDE integration.

---

## The 10 Domains Overview

| Domain # | Domain Name | Scope & Operational Focus |
|---|---|---|
| **Domain 1** | Session & Lifecycle Boundary | Process startup, workspace initialization, cold/warm start, and termination |
| **Domain 2** | Ingress & User Intent | External prompts, slash-command expansion, multimodal attachments |
| **Domain 3** | Model Inference & Egress | Pre/post LLM dispatch, token budgeting, prompt injection defense, model switching |
| **Domain 4** | Tool Gating & Execution | Tool pre-dispatch, TOCTOU verification, execution auditing, failure handling |
| **Domain 5** | Network & Egress Perimeter | Kernel/socket-level network interception, SSRF defense, traffic telemetry |
| **Domain 6** | Subagent & Delegation | Multi-agent task delegation, capability attenuation, Confused Deputy defense |
| **Domain 7** | Multi-Agent Coordination | Persistent task queues, milestone synchronization, teammate idle notifications |
| **Domain 8** | Memory & Long-Term Context | Vector memory persistence, memory poisoning defense, context compaction |
| **Domain 9** | Workspace, Filesystem & Rules | Rules loading (`.agents/rules`), directory binding, worktree isolation, config tamper defense |
| **Domain 10** | UI, MCP & Interaction | MCP form elicitation, streaming terminal display, system notifications, out-of-band kill-switch |

---

## The 39 Canonical Hook Points

### Domain 1: Session & Lifecycle Boundary
1. **`Setup`** (⚪ General): Fired during environment initialization before session startup (mode: `init`, `maintenance`, `clean`). Validates lockfile hashes (`package-lock.json`).
2. **`SessionStart` / `SessionInit`** (🔴 **Gate 1**): Fired when runtime initializes session. Inspects environment variables (`LD_PRELOAD`, rogue proxies), host fingerprint, and IdP token claims.
3. **`SessionEnd`** (⚪ General): Fired when session terminates (`user_exit`, `inactivity_timeout`, `fatal_error`, `policy_revoked`).

### Domain 2: Ingress & User Intent
4. **`UserPromptSubmit`** (🔴 **Gate 2**): Fired upon user prompt acceptance before agent planning. Scans for direct prompt injection, jailbreaks, and sensitive data ingress.
5. **`UserPromptExpansion`** (⚪ General): Fired when expanding slash-commands, prompt templates, or skill presets into full conversational context.

### Domain 3: Model Inference & Egress
6. **`PreModelSwitch`** (⚪ General): Fired when runtime switches models mid-session (e.g. escalating from Haiku to Sonnet/Opus).
7. **`PostModelSwitch`** (⚪ General): Fired after model switch resolves, verifying model parameter alignment.
8. **`BeforeModelRequest` / `PreModelCall`** (🔴 **Gate 3**): Fired immediately before dispatching prompt to LLM provider. Evaluates model egress DLP and system prompt tampering.
9. **`AfterModelResponse` / `PostModelCall`** (🔴 **Gate 4**): Fired upon receiving terminal LLM completion. Enforces output guardrails and hallucination detection.

### Domain 4: Tool Gating & Execution
10. **`ToolDiscovery`** (⚪ General): Fired when registering or dynamically discovering available tools from MCP servers or plugins.
11. **`PreToolUse`** (🔴 **Gate 5**): Fired immediately before tool execution. Enforces TOCTOU bait-and-switch defense via RFC 8785 JCS `content_identity` and triggers Asynchronous HITL escalation (`decision: "ask"`).
12. **`PermissionRequest`** (🔴 Gate): Fired at native host authorization boundaries (filesystem permissions, bash execution approval).
13. **`PermissionDenied`** (⚪ Observe): Emitted when a permission or authorization request is formally rejected.
14. **`PostToolUse`** (🔴 **Gate 6**): Fired after successful tool execution. Inspects tool output for sensitive data leaks or secondary payload injection.
15. **`PostToolUseFailure`** (⚪ General): Fired when a tool returns a non-zero exit code or network timeout.

### Domain 5: Network & Egress Perimeter
16. **`PreNetworkAccess`** (🔴 **Gate 7**): Fired before outbound network socket establishment. Blocks SSRF targeting cloud metadata (`169.254.169.254`) and internal subnets.
17. **`PostNetworkAccess`** (🔴 **Gate 8**): Fired after socket closes. Records bytes transmitted/received, connection status, and DNS resolution data.

### Domain 6: Subagent & Delegation
18. **`SubagentStart` / `PreAgentCall`** (🔴 **Gate 9**): Fired before delegating subtasks to child agents. Enforces capability attenuation and inspects `delegation_chain` to prevent Confused Deputy attacks.
19. **`SubagentStop` / `PostAgentCall`** (⚪ General): Fired when child agent completes its subtask or reaches a terminal state.

### Domain 7: Multi-Agent Coordination & Backlog
20. **`TaskCreated`** (⚪ General): Fired when an agent creates a task in a project management queue (e.g. GitHub Issues, Jira).
21. **`TaskCompleted`** (⚪ General): Fired when a backlog task item is marked completed.
22. **`TeammateIdle`** (⚪ General): Fired when an autonomous teammate finishes its workload and becomes available for new task assignment.

### Domain 8: Memory & Context Management
23. **`PreMemoryWrite`** (🔴 **Gate 10**): Fired before writing embeddings or state to long-term memory. Prevents memory poisoning and cross-session sleeper instruction insertion.
24. **`PostMemoryWrite`** (⚪ General): Fired after long-term memory persistence resolves.
25. **`PreCompact`** (⚪ General): Fired before conversation context compaction, archiving uncompressed history.
26. **`PostCompact`** (⚪ General): Fired after context compaction, verifying preservation of essential system rules.

### Domain 9: Workspace, Filesystem & Rules
27. **`InstructionsLoaded`** (⚪ General): Fired when `.agents/rules/*.md`, `CLAUDE.md`, or repository prompt rules load into context.
28. **`ConfigChange`** (🔴 **Gate 11**): Fired before altering configuration files (`settings.json`, MCP server definitions). Prevents supply-chain hijacking.
29. **`CwdChanged`** (⚪ General): Fired when working directory changes (`cd`), reloading environment variables.
30. **`DirectoryAdded`** (⚪ General): Fired when a new workspace folder is bound to the session.
31. **`FileChanged`** (⚪ General): Fired when watched files on disk are modified, triggering automated linting or testing.
32. **`WorktreeCreate`** (⚪ General): Fired when initializing an isolated Git worktree for sandbox operations.
33. **`WorktreeRemove`** (⚪ General): Fired when dismantling an isolated Git worktree upon task completion.

### Domain 10: UI, MCP & Emergency Control Plane
34. **`Elicitation`** (⚪ General): Fired when an MCP tool requests interactive human input or clarification form.
35. **`ElicitationResult`** (⚪ General): Fired after human responds to MCP elicitation, sanitizing input before submission.
36. **`MessageDisplay`** (⚪ General): Fired during streaming token rendering to terminal or UI.
37. **`Notification`** (⚪ General): Fired when the agent issues desktop banners, sound alerts, or webhook pings.
38. **`Stop`** (⚪ General): Fired at turn completion.
39. **`SessionRevoke`** (🔴 **Gate 12**): Out-of-band asynchronous kill-switch from enterprise SOC/SIEM to abort compromised sessions immediately.
