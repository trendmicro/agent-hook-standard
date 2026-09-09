---
sidebar_position: 5
---

# Security considerations

Hook payloads can contain user prompts, filesystem paths, source code, tool
arguments, tool outputs, environment details, and credentials. Hosts, adapters,
and handlers MUST treat all event data as untrusted input and SHOULD minimize
the values they expose, persist, or transmit.

## Policy authority

An Agent Hook `allow` decision only passes that handler's gate. It MUST NOT
bypass native approval, sandbox, organization, managed-policy, or platform
restrictions. A `deny` reason should be useful to the agent but MUST NOT expose
secrets or protected policy details. An `ask` decision must use a host approval
flow; non-interactive hosts MUST deny instead of assuming consent.

## Handler isolation and transport

Agent Hook does not standardize execution isolation or transport. Hosts SHOULD
run handlers with least privilege, provide only the working-directory and
environment access they require, set finite timeouts, and restrict outbound
network destinations. Adapters SHOULD avoid putting credentials into command
arguments, output, or persisted diagnostics.

## Failure and telemetry

The 0.1 default is fail open: an unavailable or malformed handler response
does not become a denial. Hosts SHOULD record a minimal diagnostic with the
event ID, event type, handler identity, and failure class. They SHOULD redact
or omit prompt text, tool data, secrets, and personal data from those records.

Handlers SHOULD validate the event schema before applying a security decision
and SHOULD return only one correlated response. A response for a different
event ID is invalid and must fail open under the core protocol.
