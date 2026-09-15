# RFCs

Formal proposals for the Agent Hook Spec live in this directory. Start by
opening an RFC Proposal in [GitHub Discussions](https://github.com/trendmicro/agent-hook-unity/discussions), then submit a numbered RFC pull request using
[`0000-template.md`](0000-template.md).

RFC numbers are four digits and assigned in sequence. Do not reuse a number.
Accepted RFCs remain here as the decision record; their resulting normative
content belongs in [`../spec/`](../spec/README.md).

See [GOVERNANCE.md](../GOVERNANCE.md) for review, voting, and status rules.

## Response inspection proposal

[RFC 0005](./0005-network-response-delivery-inspection.md) proposes extending
`PostNetworkAccess` to inspect, replace, or withhold buffered response content
before an agent receives it. It keeps the Pre/Post pair and all 18 Core event
names, preserves Observe-only implementations and the fail-open default, and
requires explicit configuration for the revised control semantics. The draft
awaits the prerequisite Discussion and formal review; the current specification
and schemas do not yet implement it.
