---
sidebar_position: 2
---

# Core protocol

## Status and terminology

This document defines the Agent Hook 0.1 draft. The key words **MUST**,
**MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**,
and **OPTIONAL** in this document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they
appear in all capitals.

A **host** is the agent runtime that observes lifecycle activity. An
**adapter** translates between a host's native hook facility and this contract.
A **handler** consumes an Agent Hook event and returns an Agent Hook response.
An **invocation** is one host delivery of one event to one handler.

Agent Hook standardizes the event and response documents only. It does not
standardize handler discovery, configuration files, matcher grammar, invocation
order, process lifecycle, timeout values, authentication, or a transport
binding. A command handler receiving one JSON document on standard input and
writing one JSON response on standard output is a useful non-normative adapter
pattern, modeled after existing agent runtimes.

## Event envelope

An event MUST be a JSON object that validates against the
[Hook Event schema](https://trendmicro.github.io/agent-hook-standard/schemas/0.1/hook-event.schema.json).
It contains these required members:

| Member | Meaning |
| --- | --- |
| `hook_version` | The Agent Hook contract version, `0.1`. |
| `event_id` | A UUID that uniquely identifies this delivered event. |
| `event_type` | A core or extension event identifier. |
| `timestamp` | RFC 3339 time at which the host observed the event. |
| `context` | Portable session, agent, and workspace context when available. |
| `payload` | Event-specific object data. |

`context` MAY contain `session_id`, `agent_id`, and `workspace.cwd`. Hosts MUST
omit unavailable context rather than invent it. Tool payloads SHOULD contain a
stable `tool_call_id`, `tool.name`, and the relevant `tool.input`,
`tool.output`, or `error` member. Tool arguments and results are JSON values,
not stringified JSON.

An event MAY contain `extensions`, as defined in the
[extension policy](./extensions.md). Hosts MUST preserve `event_id` when an
event passes through an adapter or intermediate component.

## Response envelope

A handler response MUST be a JSON object that validates against the
[Hook Response schema](https://trendmicro.github.io/agent-hook-standard/schemas/0.1/hook-response.schema.json).
It contains required `hook_version` and `event_id` members. `event_id` MUST
equal the event's `event_id`; a response with a different identifier is invalid.

The optional `decision` member has one of these values:

| Decision | Meaning for a decision-capable event |
| --- | --- |
| `allow` | The handler's gate passes. It does not override host or organization policy. |
| `deny` | The host MUST prevent the action and show or return `reason` to the agent. |
| `ask` | The host MUST use its native approval path. A non-interactive host MUST deny the action. |

`reason` is REQUIRED for `deny` and `ask`. `annotations` is an optional JSON
object for observational metadata; hosts MAY record it but MUST NOT treat it as
an instruction. `extensions` follows the extension policy.

Only a decision-capable event interprets `decision`. The initial
decision-capable event is `agent-hook.tool.pre`. A response decision on another
event MUST be ignored for control purposes, although a host MAY retain it for
diagnostics.

## Fail-open behavior

An absent response, invalid JSON, schema-invalid response, correlation mismatch,
handler error, or timeout MUST result in no Agent Hook decision. The host MUST
continue the affected operation unless an independent native policy blocks it.
Adapters SHOULD emit a diagnostic record containing the event ID, failure class,
and handler identity without retaining sensitive payload data.

This requirement controls only Agent Hook 0.1. It does not weaken host,
sandbox, administrative, or organization policy. A host requiring fail-closed
enforcement MUST use a native mechanism or a future explicitly configured
profile; it MUST NOT reinterpret an Agent Hook failure as an implicit `deny`
while claiming 0.1 default behavior.

## Versioning and conformance

`hook_version` is a major/minor contract identifier. A 0.1 implementation MUST
emit and accept exactly `0.1`; patch-only specification changes do not change
the field. Future incompatible envelopes require a new major version.

An implementation conforms as an **event producer** if it emits schema-valid
events and implements this document's required semantics. It conforms as a
**handler** if it accepts schema-valid events and emits schema-valid correlated
responses. An **adapter** conforms if it preserves core semantics while mapping
between a native hook facility and the event/response contract. Conformance does
not imply compatibility with a vendor's configuration file.
