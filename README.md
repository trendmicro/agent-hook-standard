# Agent Hook Spec

Agent Hook Spec is a community effort to define a portable lifecycle-hook
protocol for AI agents and their tooling. It will let agent builders describe
events, hook payloads, hook responses, and security telemetry using a shared,
interoperable model.

The 0.1 draft defines thirteen canonical Core `hook_event_name` values across
session and turn lifecycle, user prompts, model requests and responses, tool
use, permission outcomes, and subagent delegation. Hosts publish the Core
boundaries and gate behavior they can observe and enforce faithfully. Each
per-event capability claim is `gate`, `observe`, `partial`, or `unavailable`;
an unavailable claim is not evidence that the underlying activity did not
occur.

## Status

The repository contains an adoption-ready Agent Hook 0.1 draft proposed by
[RFC 0001](rfcs/0001-agent-hook-core-event-contract.md). It is not active until
accepted through the RFC process. Join the
[GitHub Discussions](https://github.com/trendmicro/agent-hook-standard/discussions)
to help shape it.

## Repository map

- [`rfcs/`](rfcs/README.md) — proposal process and formal RFCs.
- [`spec/`](spec/README.md) — canonical normative specification Markdown.
- [`schemas/`](schemas/README.md) — machine-readable JSON Schemas.
- [`fixtures/`](fixtures/README.md) — schema-validation fixtures.
- [`examples/`](examples/README.md) — illustrative integrations.
- [`website/`](website/) — Docusaurus source for the GitHub Pages site.

## Local setup

Install the validator and website dependencies separately:

```sh
npm ci
npm ci --prefix website
```

## Participate

Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing. The decision
process, voting rules, and RFC lifecycle are defined in
[GOVERNANCE.md](GOVERNANCE.md). For sensitive matters, follow
[SECURITY.md](SECURITY.md).

## Licenses

Specifications and documentation are licensed under
[CC BY 4.0](LICENSE-DOCS). Code, schemas, tooling, and website assets are
licensed under the [MIT License](LICENSE-CODE).
