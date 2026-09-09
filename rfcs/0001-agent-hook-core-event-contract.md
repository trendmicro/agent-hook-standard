---
title: "RFC 0001: Agent Hook 0.1 Core Event Contract"
status: Draft
discussion: "TBD — GitHub Discussion required before formal review"
review-start: TBD
review-end: TBD
maintainer-votes: []
decision: "Pending"
supersedes: []
superseded-by: []
---

# RFC 0001: Agent Hook 0.1 Core Event Contract

## Summary

This RFC proposes Agent Hook 0.1, a portable JSON contract for lifecycle-hook
events and hook responses. It defines a small native envelope, a starter event
registry, decision semantics, JSON Schemas, fixtures, and adapter guidance.
It does not standardize native settings files, discovery locations, matcher
languages, handler ordering, or execution transports.

## Motivation

Agent runtimes increasingly expose hooks for policy enforcement, observability,
and workflow automation. Claude Code, Cursor, and Gemini all expose useful
lifecycle and tool boundaries, but their event names, payload shapes,
configuration, and response conventions differ. An integration therefore needs
one implementation per runtime even when its intended policy is identical.

The common boundary is an event delivered to a handler and a structured result
returned by that handler. Standardizing that boundary permits runtimes to build
small adapters without requiring a single configuration system or runtime
architecture.

## Prior art

- [Claude Code hooks](https://code.claude.com/docs/en/hooks) provide lifecycle
  events, command/HTTP/MCP/prompt handlers, JSON input and output, and
  permission decisions.
- [Cursor hooks](https://docs.cursor.com/agent/hooks) provide JSON-over-stdio
  hooks around sessions, tools, agents, and editor activity.
- [Gemini CLI hooks](https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/reference.md)
  use JSON input/output and before/after tool lifecycle points.
- [CloudEvents](https://github.com/cloudevents/spec) demonstrates the value of
  a compact, extensible event envelope, but this RFC chooses a native contract
  closer to existing agent hook payloads.
- [AsyncAPI](https://github.com/asyncapi/spec) separates canonical Markdown,
  schemas, and examples; this repository follows that documentation pattern.

## Proposal

Adopt the normative documents in [`../spec/0.1/`](../spec/0.1/) and the
machine-readable schemas in [`../schemas/`](../schemas/). Agent Hook 0.1:

1. Defines `hook_version`, `event_id`, `event_type`, `timestamp`, `context`,
   and `payload` as the required event envelope members.
2. Defines `hook_version` and `event_id` as the required response members, and
   `allow`, `deny`, and `ask` as optional decisions.
3. Starts with five core events: session started/ended and tool pre/post/failed.
4. Defines `deny` and `ask` only for decision-capable pre-action events; all
   other events are observational.
5. Makes failed, timed-out, absent, and invalid hook responses fail open.
6. Reserves extensions for vendor-specific names and data, with adapter
   guidance rather than configuration-file compatibility claims.

The initial registry is intentionally small and may be amended through future
RFCs after implementer review.

## Compatibility impact

Existing native hook configurations remain valid and unchanged. They do not
validate as Agent Hook configuration, because configuration and handler
selection are out of scope. Adapters translate native events and responses to
the Agent Hook contract; the included Claude Code, Cursor, and Gemini mapping
is illustrative, not a compatibility guarantee for a particular product
release.

## Security and privacy impact

The proposal permits a hook to request `allow`, `deny`, or `ask`, which makes
the host responsible for preserving policy authority. An `allow` result never
overrides host, organization, sandbox, or administrative policy. An `ask`
result must reach a native approval mechanism or be denied in a non-interactive
host. Event payloads may contain prompts, paths, tool arguments, outputs, and
credentials; adapters and handlers must treat them as untrusted sensitive data.

The default on handler failure is intentionally fail open for availability. A
runtime that requires fail-closed enforcement must use a native policy feature
or define a future, explicitly configured profile.

## Alternatives considered

- **Adopt CloudEvents directly.** Rejected for 0.1 because existing hook
  payloads are closer to a native JSON shape and a CloudEvents binding would
  add a second vocabulary without solving hook decisions.
- **Standardize configuration and transport.** Deferred because native
  discovery, trust, process isolation, and handler execution models materially
  differ across runtimes.
- **Observation-only hooks.** Rejected because pre-action policy decisions are
  a primary cross-runtime use case.
- **A broad lifecycle registry.** Deferred so the first interoperable surface
  can be validated before standardizing model, prompt, filesystem, task, and
  worktree events.

## Acceptance checklist

- [ ] A GitHub Discussion is linked in the front matter.
- [ ] The public review window has run for at least 14 calendar days.
- [ ] The canonical specification, schemas, fixtures, examples, and website
  documentation are reviewed together.
- [ ] `npm run validate` and `npm run build` pass.
- [ ] Maintainer votes and decision rationale are recorded below.

## Decision record

The originating Discussion, review dates, votes, objections, and final
rationale will be recorded here when the RFC is decided.
