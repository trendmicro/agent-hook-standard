---
slug: /
sidebar_position: 1
---

import Link from '@docusaurus/Link';

# Agent Hook Spec

Agent Hook Spec is a community effort to define a portable lifecycle-hook
protocol for AI agents and their tooling. A shared protocol can make it easier
for builders to expose compatible events, payloads, and hook responses.

## Current status

The repository contains an adoption-ready **Agent Hook 0.1 draft** proposed by
RFC 0001, with standard network, memory, and configuration events proposed by
RFC 0004. It defines a portable event and response contract, schemas, fixtures,
examples, and adapter guidance. It is not active until accepted through the
public RFC process.

The draft intentionally standardizes neither settings-file formats nor handler
execution. Agent runtimes can map their native hooks to the shared event
contract without giving up their own discovery, matching, trust, and policy
models.

The <Link to="/specification/0.1/events">event registry</Link>
contains eighteen standard events. A host can support the events it can expose
faithfully and declare the rest unavailable. Local agents can adopt the event
contract without enterprise identity, remote approval, or audit services.

## Get involved

- Bring a use case or question to [GitHub Discussions](https://github.com/trendmicro/agent-hook-unity/discussions).
- Read the [RFC process](./governance.md) before proposing a protocol change.
- Review the [conformance approach](./conformance.md) for the planned schema
  and fixture conventions.
