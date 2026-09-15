---
slug: /
sidebar_position: 1
---

import Link from '@docusaurus/Link';

# Agent Hook Spec

Agent Hook Spec defines a shared lifecycle event and response contract for AI
agents and their tooling. It gives runtime builders and handler authors a
common vocabulary for describing an operation, correlating its events, and
identifying the boundaries at which a handler can influence execution.

## Who does what

| Role | Responsibility |
| --- | --- |
| Host | Observe the actual lifecycle boundary, declare its capabilities, and apply supported controls through its native runtime. |
| Adapter | Translate native callbacks into faithful Agent Hook documents and map supported responses back to the host. An adapter may be part of the host. |
| Handler | Consume an event and return a schema-valid response correlated to that delivery. |

```text
Host lifecycle -> Adapter -> Agent Hook event -> Handler
Host           <- Adapter <- Correlated response <- Handler
```

The return path carries control only at a supported Gate. Native approval,
sandbox, organization, and host restrictions remain authoritative. This diagram
describes responsibilities; it does not prescribe separate processes, a
transport, or the order of multiple handlers.

## What the contract guarantees

The <Link to="/specification/0.1/events">event registry</Link> defines eighteen
Core events: seven **Gate** events and eleven **Observe** events. Gate events
can control a pending operation when the host declares and implements that
capability. Observe events report a lifecycle boundary; a response does not
turn them into preventive controls.

Each host declares every Core event as `gate`, `observe`, `partial`, or
`unavailable`. A related native callback is insufficient if its timing, data,
correlation, or control cannot meet the event's requirements. A `partial` or
`unavailable` signal cannot be emitted as a normalized Core event. See the
<Link to="/capabilities">capability guide and complete example</Link>.

The contract standardizes event names, document shapes, correlation, and
event-specific control semantics. Settings files, handler discovery, matching,
execution order, process lifecycle, authentication, and transport remain host
concerns. An interoperable document does not establish identical multi-handler
policy composition across hosts.

The 0.1 draft treats missing, invalid, timed-out, or errored handler responses
as providing no Agent Hook control result. For an event declared `gate`, the
default is **fail open**: the operation continues unless an independent native
policy blocks it. Observe responses have no control effect. The contract does
not provide a sandbox or guarantee that every
internal runtime or provider operation is visible. In particular, the Observe
events for completed model and tool results do not promise output filtering
or rollback. The <Link to="/specification/0.1/core#host-obligations">host
obligations</Link> and <Link to="/specification/0.1/security">security
considerations</Link> explain these boundaries.

## Current status

The repository contains an unaccepted **Agent Hook 0.1 draft** proposed by
RFC 0001, with standard network, memory, and configuration events proposed by
RFC 0004. It defines a portable event and response contract, schemas, fixtures,
examples, and adapter guidance. It is not active until accepted through the
public RFC process.

Local agents can use the draft without enterprise identity, remote approval,
or audit services. Earlier 0.1 schemas do not recognize the five added network,
memory, and configuration events; use compatible schemas and configured
handlers as described in the
<Link to="/specification/0.1/core#versioning-and-conformance">versioning rules</Link>.

This contract is neither a byte-for-byte Claude Code hook interface nor the
separate [Responsible AI Agent Hooks contract](https://responsibleai.github.io/agent-hooks/).
The latter also uses `agent-hooks/0.1`, but its `interception_point` context and
verdict documents are different from this draft's `hook_event_name` events and
correlated responses. The identifier alone does not establish compatibility.
This clarification does not change the identifier or either contract's behavior.

## Start reading

| Reader | Start here |
| --- | --- |
| Runtime or adapter implementer | <Link to="/specification/0.1/core#host-obligations">Host obligations</Link>, then the <Link to="/capabilities">capability declaration guide</Link>. |
| Handler author | <Link to="/responses">Response reference</Link>, alongside the <Link to="/specification/0.1/events">event registry</Link>. |
| Reviewer or adopter | <Link to="/specification/0.1">Draft overview</Link> and <Link to="/conformance">conformance evidence and limits</Link>. |

The response reference and capability example are informative guides to the
canonical specification. They identify unresolved behavior without defining
new controls or claiming tested support for a real host.

### Draft response-inspection proposal

[RFC 0005 / PR #8](https://github.com/trendmicro/agent-hook-unity/pull/8) proposes
extending `PostNetworkAccess` to inspect, replace, or withhold response content
before an agent receives it. It keeps the existing Pre/Post pair and all
eighteen event names. The RFC is a draft awaiting the prerequisite Discussion
and formal review; it has not been adopted. The published 0.1 draft still
defines `PostNetworkAccess` as Observe and ignores its control responses.

## Get involved

- Bring a use case or question to [GitHub Discussions](https://github.com/trendmicro/agent-hook-unity/discussions).
- Read the [RFC process](./governance.md) before proposing a protocol change.
- Review the [conformance approach](./conformance.md) for the existing schema
  and fixture checks and the additional runtime evidence an adapter needs.
