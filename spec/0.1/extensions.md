---
sidebar_position: 4
---

# Extensions

Extensions preserve portability by keeping host-specific semantics outside core
members and core event types.

## Extension data

`extensions` is an object whose property names MUST be reverse-DNS namespaces,
such as `com.example.policy` or `io.acme.agent`. The namespace owner defines
the JSON value. A consumer that does not recognize an extension MUST ignore it
without failing the core event or response.

Core producers MUST NOT place vendor-specific values directly in `context` or
`payload` when an extension namespace can contain them. Extensions MUST NOT
change the meaning of a core member or cause `allow` to override independent
host policy.

## Extension event types

Core event types begin with `agent-hook.` and are reserved for this
specification. A vendor extension event type MUST contain at least three
dot-separated components and begin with a reverse-DNS namespace, for example
`com.example.agent.prompt.expanded`.

An adapter MAY map a native event that has no core equivalent to an extension
event. It MUST document the event's native source, payload members, control
capability, and privacy implications. An extension that proves broadly useful
may be proposed as a future core event through an RFC.
