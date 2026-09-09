---
sidebar_position: 4
---

# Extensions

Extensions preserve portability by keeping host-specific semantics outside Core
members and Core `hook_event_name` values.

## Extension data

`extensions` is an object whose property names MUST be reverse-DNS namespaces,
such as `com.example.policy` or `io.acme.agent`. The namespace owner defines
the JSON value. A consumer that does not recognize an extension MUST ignore it
without failing the core event or response.

Core producers MUST NOT place vendor-specific values directly in a Core field
when an extension namespace can contain them. Extensions MUST NOT change the
meaning of a Core member, correlation identifier, or capability mode, and MUST
NOT cause an extension response to override independent host policy or convert
an Observe event into a Gate.

## Extension hook event names

Core `hook_event_name` values are reserved PascalCase names defined by this
specification. A vendor extension `hook_event_name` MUST use the registered
`x-<vendor>/<PascalCaseEventName>` form, for example
`x-example/AgentPromptExpanded`. An extension event uses the same flat common
envelope and MUST NOT reuse a Core name with different semantics.

An adapter MAY map a native event that has no core equivalent to an extension
event. It MUST document the event's native source, required flat members,
correlation behavior, capability mode, control boundary, and privacy
implications. An extension that proves broadly useful may be proposed as a
future Core event through an RFC.
