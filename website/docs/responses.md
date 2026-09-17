---
sidebar_position: 2
---

import Link from '@docusaurus/Link';

# Response reference

This informative guide brings together the current response schema and event-specific
behavior. The <Link to="/specification/0.1/core#response-envelope">Core protocol</Link>,
<Link to="/specification/0.1/events#gate-and-observe-semantics">event registry</Link>, and
<Link to="/specification/0.1/security#policy-authority">security requirements</Link>
remain authoritative. This page introduces no new wire fields or control semantics.

## Read a response in context

1. Validate the JSON against the <Link to="pathname:///schemas/0.1/hook-response.schema.json">response schema</Link>.
2. Match `event_id` to the delivered event. If `hookSpecificOutput` is present,
   also match its `hookEventName` to the request's `hook_event_name`.
3. Consult the event's classification and the host's <Link to="/capabilities">capability declaration</Link>.
   Portable control requires both a Core Gate and a declared `gate` capability.
4. Apply only the event-specific control semantics below. Hook permission never
   overrides native approval, sandbox, organization, managed-policy, or platform restrictions.

A response can pass the schema and still fail the request/response pairing checks.
An incorrect event ID or event name is invalid and follows the
<Link to="/specification/0.1/core#fail-open-behavior">existing fail-open rule</Link>:
there is no Agent Hook control result; a declared Gate continues unless independent
native policy blocks it. Missing responses, malformed JSON, schema errors, handler
errors, and timeouts follow that same rule.

## Control by Gate

Paths in this table are relative to the response root. To establish clean separation
between the **control plane** (authorization decisions) and the **data plane**
(payload mutations), a handler MAY provide a top-level `decision` (`allow`, `deny`,
`ask`, `defer`, or legacy `block`) and an optional `reason` (required for `deny` or `block`).
When no rewrite is needed, `hookSpecificOutput` may be omitted entirely. For backward
compatibility, `permissionDecision` inside `hookSpecificOutput` remains accepted.

| Gate | Canonical control path | Controlled boundary and effect | Defined rewrite support (`hookSpecificOutput`) |
| --- | --- | --- | --- |
| `SessionStart` | `decision: "allow"` or `"deny"` | Controls whether session context initialization may proceed before agent work starts. | None. |
| `UserPromptSubmit` | `decision: "allow"`, `"deny"`, or legacy `"block"` | Prevents prompt execution (`deny` or `block`), or surgically replaces prompt content (`allow` + `updatedPrompt`). | `hookSpecificOutput.updatedPrompt` replaces the accepted prompt. |
| `BeforeModelRequest` | `decision: "allow"`, `"deny"`, `"ask"`, or `"defer"` | Controls the complete model request before provider dispatch. | `hookSpecificOutput.updatedMessages` replaces messages at this boundary. |
| `AfterModelResponse` | `decision: "allow"` or `"deny"` | Controls the completed model response before UI rendering or context ingestion (when declared `gate`). | `hookSpecificOutput.updatedResponse` replaces the model output. |
| `PreToolUse` | `decision: "allow"`, `"deny"`, `"ask"`, or `"defer"` | Controls the proposed tool invocation before any effect occurs. | `hookSpecificOutput.updatedInput` replaces tool input at this boundary. |
| `PermissionRequest` | `decision: "allow"` or `"deny"` | Controls the native approval request. | The nested decision may carry `updatedInput` and `updatedPermissions`. |
| `PostToolUse` | `decision: "allow"` or `"deny"` | Controls the completed tool invocation before context ingestion (when declared `gate`). | `hookSpecificOutput.updatedOutput` replaces tool output. |
| `PreNetworkAccess` | `decision: "allow"`, `"deny"`, `"ask"`, or `"defer"` | `deny` prevents the pending application request from being dispatched. | None; content-rewriting controls have no effect. |
| `PostNetworkAccess` | `decision: "allow"` or `"deny"` | Controls response delivery before caller access (when declared `gate` on buffered transport). | None; response body inspection and replacement are deferred to RFC 0005. |
| `PreMemoryWrite` | `decision: "allow"`, `"deny"`, `"ask"`, or `"defer"` | `deny` prevents the pending durable write from becoming persistent or visible. | `hookSpecificOutput.updatedContent` replaces proposed content. |
| `PreConfigChange` | `decision: "allow"`, `"deny"`, `"ask"`, or `"defer"` | `deny` prevents the pending effective configuration mutation. | None; content-rewriting controls have no effect. |
| `SubagentStart` | `decision: "allow"` or `"deny"` | Controls child agent delegation before executable work is dispatched. | None. |

A handler responding with control or mutation intent MUST provide a top-level
`decision`. When present, top-level `decision` is canonical across all Gates, and
hosts MUST ignore legacy nested decisions (`permissionDecision`, `decision.behavior`).
For Post Gates (`AfterModelResponse`, `PostToolUse`, `PostNetworkAccess`), control
governs delivery to caller, rendering to user, or ingestion into context; it does
not roll back completed model, tool, or network executions.

An `allow` only passes that handler's native gate. A response requesting approval
uses a host approval flow; non-interactive hosts treat it as `deny` unless they support
asynchronous turn suspension awaiting an approval token. Resumption token formats,
issuance, lifetime, and endpoints are host-specific implementation mechanisms.
For `PreNetworkAccess`, `PreMemoryWrite`, and `PreConfigChange`, Core explicitly
defines `ask` as the existing native approval flow and `defer` as leaving resolution
to native approval or policy, without counting as approval. A shared `defer` workflow
for model and tool Gates is not specified in this draft.

For data plane mutations (`updatedPrompt`, `updatedInput`, `updatedResponse`,
`updatedOutput`, `updatedContent`), the host MUST apply its native validation rules
before committing the change. If validation fails, the host MUST fail closed
(terminating the operation or denying execution) and MUST NOT silently fall back
to the sensitive or unredacted original payload.

For those same three Gates, the decision covers the presented operation, target,
and proposed values. A change before dispatch or mutation requires Gate evaluation
again. For `PreMemoryWrite`, `updatedContent` permits surgical content sanitization
before persistent storage. See the
<Link to="/specification/0.1/events#gate-and-observe-semantics">mutation preconditions</Link>.

For a declared `observe` capability, all response control fields are ignored for
control purposes, including on Core events otherwise classified as Gates. The host
may retain response data for diagnostics or observation. A `partial` or `unavailable`
capability cannot emit a normalized Core event.

## Field reference

All fields are optional except where indicated. Optional typed fields do not accept
`null` unless their schema explicitly permits it; omission is different from a
provided value. The root object rejects unknown properties. `hookSpecificOutput`,
its nested `decision`, and `metadata` accept additional properties, but acceptance
does not assign portable semantics. Use namespaced `extensions` for vendor data.

### Envelope and common fields

“Open” below means that the schema accepts the field but the draft does not define
the stated portable behavior. These are documentation labels, not wire values.

| Field | Schema shape | Current meaning or boundary |
| --- | --- | --- |
| `spec` | Required; exactly `"agent-hooks/0.1"` | Identifies the contract; not native response compatibility. |
| `event_id` | Required UUID string; schema pattern accepts UUID version nibble 1–8 and variant 8, 9, a, or b, case-insensitively | Equals the delivered event ID; identifies the delivery, not the underlying operation. |
| `decision` | `"allow"`, `"deny"`, `"ask"`, `"defer"`, or legacy `"block"` | Canonical control plane decision across all Gates. When present, hosts ignore legacy nested decisions. |
| `reason` | Nonempty string; required with `decision: "deny"` or `"block"` | Explains the denial or block decision; avoid secrets or protected policy details. |
| `continue` | Boolean | Open: portable stop/continue behavior and precedence against event-specific decisions. |
| `stopReason` | String | Open: relationship to `continue`, required combinations, and consumer. |
| `systemMessage` | String | Open: intended UI/model/diagnostic consumer and authority. |
| `terminalSequence` | String | Open: interpretation, destination, and terminal handling. |
| `suppressOutput` | Boolean | Open: which output is suppressed and by which consumer. |
| `async` | Exactly `true` when present; `false` is invalid | Open: asynchronous execution behavior; does not establish asynchronous approval. |
| `asyncTimeout` | Number, minimum 0 | Open: unit, timing boundary, and relationship to `async`; schema alone imposes no dependency. |
| `hookSpecificOutput` | Object; requires `hookEventName` | Contains event-specific fields listed below. |
| `metadata` | Object | Optional response diagnostics; no enforcement or durable audit guarantee is defined. |
| `extensions` | Object with reverse-DNS property names | Namespace-owned JSON values; unknown namespaces are ignored under the <Link to="/specification/0.1/extensions">extension policy</Link>. Cannot override Core semantics or policy. |

### Event-specific fields

Paths here are relative to `hookSpecificOutput`.

| Field | Schema shape | Current meaning or boundary |
| --- | --- | --- |
| `hookEventName` | Required; one of the 18 Core names or `x-<vendor>/<PascalCaseEventName>` matching the schema | Equals the request's `hook_event_name`; extension events follow their documented mapping. |
| `permissionDecision` | `allow`, `deny`, `ask`, or `defer` | Legacy fallback control for Gates when root `decision` is omitted. |
| `permissionDecisionReason` | String | Optional explanation for that legacy decision; not a separate control. |
| `updatedPrompt` | String | Prompt replacement for `UserPromptSubmit`. Replaces the submitted prompt. |
| `updatedInput` | Object; arbitrary properties | Tool-input replacement for `PreToolUse`. Replaces proposed tool input before execution. |
| `updatedResponse` | Object; arbitrary properties | Model response replacement for `AfterModelResponse` when declared `gate`. Sanitizes model response before UI rendering or context ingestion. |
| `updatedOutput` | Object; arbitrary properties | Tool output replacement for `PostToolUse` when declared `gate`. Sanitizes tool result before context ingestion. |
| `updatedContent` | Any JSON value | Memory content replacement for `PreMemoryWrite`. Sanitizes content before durable persistence. |
| `updatedMessages` | Array; unconstrained items | Message replacement for `BeforeModelRequest`. Replaces messages dispatched to provider. |
| `additionalContext` | String | Open: consumer, insertion point, and authority; no universal model-context mutation is defined. |
| `decision` | Object; requires `behavior` | Native approval control for `PermissionRequest`; distinct from root `decision`. |
| `decision.behavior` | `allow` or `deny` | Controls that native approval request, subject to independent policy. |
| `decision.updatedInput` | Object; arbitrary properties | Optional approval-boundary input update; portable validation/application rules remain open. |
| `decision.updatedPermissions` | Array; unconstrained items | Optional native permission updates; not a portable permission policy language. |
| `decision.message` | String | Optional native approval message; consumer/display behavior remains open. |
| `decision.interrupt` | Boolean | Optional native-shaped field; portable interruption behavior and interaction with `behavior` remain open. |

### Metadata fields

| Field under `metadata` | Schema shape | Current meaning or boundary |
| --- | --- | --- |
| `audit_id` | Nonempty string | Audit correlation label; producer, persistence, and retrieval are not standardized. |
| `latency_ms` | Number, minimum 0 | Latency value named in milliseconds; the measured interval is not standardized. |
| `triggered_rules` | Array of strings | Rule labels; no common rule namespace or ordering is defined. |

Additional metadata values are schema-permitted. Retention is optional and remains
subject to <Link to="/specification/0.1/security#failure-and-telemetry">data minimization guidance</Link>.

## Correlated examples

Each example assumes a separate illustrative delivery with the stated request
`hook_event_name` and `event_id: "11111111-1111-4111-8111-111111111111"`.
The repeated ID is for readability across independent examples; real deliveries
have unique IDs. These response documents illustrate shape and existing semantics,
not execution evidence for a particular host.

### Block an accepted prompt

Request event: `UserPromptSubmit`. `hookSpecificOutput` is unnecessary for this control.

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "decision": "block",
  "reason": "This request exceeds the permitted task scope."
}
```

### Deny tool execution

Request event: `PreToolUse`. For a declared Gate, the denied invocation does not start.

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "The proposed tool action exceeds the permitted task scope."
  }
}
```

### Deny a native approval request

Request event: `PermissionRequest`. The nested `behavior` belongs to this event;
it is not interchangeable with `permissionDecision`.

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "deny" }
  }
}
```

### Replace model messages before dispatch

Request event: `BeforeModelRequest`. This example assumes the host's model mapping
supports these illustrative message objects; the schema itself does not prescribe
their structure. `allow` does not bypass independent native policy.

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "hookSpecificOutput": {
    "hookEventName": "BeforeModelRequest",
    "permissionDecision": "allow",
    "updatedMessages": [{ "role": "user", "content": "Summarize the public project overview." }]
  }
}
```

### Return metadata for an observation

Request event: `PostToolUse`. This response can support optional diagnostics;
it cannot change the completed invocation.

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "metadata": {
    "audit_id": "example-observation-1",
    "triggered_rules": ["tool-observation"]
  }
}
```

## Decisions still needed

The draft does not establish precedence for conflicting common and event-specific
controls, a universal default for every valid response that omits controls,
portable rewrite validation, or multi-handler composition. Schema acceptance is
not a substitute for those decisions. Native-shaped fields also do not imply
byte-for-byte Claude Code response compatibility. See
<Link to="/specification/0.1/core#boundaries-still-open-in-01">boundaries still open in 0.1</Link>
for the distinction between host-specific behavior and changes requiring a future proposal.
