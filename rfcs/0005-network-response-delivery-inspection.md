---
title: "RFC 0005: Inspect network response bodies before delivery"
status: Draft
discussion: "Pending — repository Discussions are not enabled"
review-start: "Not started"
review-end: "Not scheduled"
maintainer-votes: []
decision: "Pending"
supersedes: []
superseded-by: []
---

# RFC 0005: Inspect network response bodies before delivery

## Summary

Propose `BeforeNetworkResponseDelivery`, a Core Gate for inspecting a complete
network response body before an agent or tool caller can consume it. A valid
denial prevents delivery of that body. A host may implement quarantine under
its own storage and retention policy.

Preserve `PostNetworkAccess` as the Observe event for a request's terminal
network result. Receiving a response successfully and permitting its content
to reach an agent are separate outcomes: a completed HTTP response can be
recorded as network `success` even when delivery of its body is denied.

This RFC targets a subsequent revision of the **unaccepted Agent Hook 0.1
draft**. It does not add an event to the current schemas or registry, which
still contain 18 Core events. The proposed name, fields, and semantics below
are for review, not a claim of current conformance or vendor endorsement.
Formal review has not started. A prior GitHub Discussion and the review window
required by [GOVERNANCE.md](../GOVERNANCE.md) must precede a decision; repository
Discussions are currently disabled. This Draft PR is preparatory material.

## Motivation

A network destination may be permitted while its response contains content
that a host policy prohibits an agent from consuming. For example, a download
from an allowed host may contain an executable where only text is permitted.
The host needs a boundary at which it still controls delivery of the body and
can apply a handler's decision.

The current [network events](../spec/0.1/events.md#prenetworkaccess) answer two
different questions:

- `PreNetworkAccess`: may this application-level request be dispatched?
- `PostNetworkAccess`: how did this started request finish at the network
  protocol boundary?

Neither event currently defines a decision about releasing a complete buffered
response body to a consumer. Giving `PostNetworkAccess` that meaning would
combine terminal network telemetry with a separate consumer-delivery decision.
A separate event makes the protection and its limits explicit while keeping
existing handlers' interpretation of network results.

## Proposal

### Scope and terminology

The requirements in this section describe the **proposed** contract. The key
words MUST, MUST NOT, SHOULD, and MAY carry the same meaning as in the
[Core protocol](../spec/0.1/core.md#status-and-terminology).

The **consumer** is the agent, tool caller, or another downstream recipient
whose access to the response body the host controls. The **trusted mediator**
is the host component that receives, buffers, and submits the body to an
authorized handler. The mediator and handler are outside that protected
consumer boundary.

Each Gate concerns one delivery attempt to one consumer, identified by
`delivery_id` and `consumer_id`. It does not authorize every possible recipient
of that network response. A host MUST assign a stable, nonempty `consumer_id`
within a session and distinguish separately controlled recipients. It MUST
document what a consumer represents and how that identity maps to native
agents, tool callers, or other recipients; no global identity registry is
introduced.

This first proposal covers one complete, finite response body buffered before
consumer access. It does not define:

- Incremental release or per-chunk approval for a streaming response.
- Inspection or rewriting of all HTTP headers, cookies, or protocol metadata.
- Body replacement, sanitization, a malware detector, or a claim that a
  particular inspection establishes content safety.
- Kernel or socket enforcement, rollback of a remote action, or prevention of
  data already sent in the original request.
- Quarantine storage, retention, a release-from-quarantine API, cryptographic
  signing, remote approval tokens, or an asynchronous HITL protocol.

Native mechanisms may provide these additional capabilities under a separate
contract. In particular, a native quarantine may retain or delete denied
content; the portable effect proposed here is **withholding its delivery**.

### Event boundary

Unless stated otherwise, per-event requirements apply only when the host
declares this event `gate` or `observe`. A `partial` or `unavailable`
capability MUST NOT emit it as a normalized Core event.

A producer MUST emit `BeforeNetworkResponseDelivery` after it has received
and buffered one complete application-level response body, and before any
bytes of that body become available to the consumer. A host declaring `gate`
MUST retain control of that buffer until the decision or failure handling
described below permits delivery or denies it.

Consumer access includes a readable temporary file, shared memory, stdout, a
callback, or a stream, as well as returning bytes directly. A host MUST NOT
claim that this Gate protected a complete response if it already exposed any
part of that body to the consumer. A transport that receives chunks may
qualify if the host buffers the entire finite body and releases none of it
before resolving this Gate; that is not incremental streaming delivery.

The event applies when a complete response body is about to be delivered,
including an empty body or the body of a complete HTTP error-status response.
A transport failure or interruption yielding an incomplete body is outside
this proposal's delivery scope. Hosts MUST NOT label a partial body as complete
to emit this event; handling that partial result remains a native concern.

A request whose body is never offered for delivery does not need this event.
For a host declaring `gate`, every complete-body delivery in its declared
configuration MUST pass this boundary. A refusal by an independent native
policy may stop delivery before any handler invocation.

### Relationship to the existing network events

For a request whose complete body will be delivered, a host supporting all
three boundaries follows this order:

```text
PreNetworkAccess (request dispatch decision)
  -> request sent; complete response received into a trusted buffer
  -> PostNetworkAccess (terminal network result, Observe)
  -> BeforeNetworkResponseDelivery (body delivery decision)
       allow / resolved native approval -> release the evaluated body
       deny                            -> withhold the body
       handler failure                 -> Core fail-open / native policy
```

`PostNetworkAccess` MUST describe the actual terminal network result. A later
delivery denial MUST NOT relabel a completed transfer as network `failure` or
`interrupted`, or cause another terminal Post event. If the transfer itself
fails or is interrupted, its Post event reports that result, and the complete
body Gate does not apply.

The three capabilities are independent. A host can support this proposed
delivery boundary without a faithful native request-dispatch hook; it MUST
declare the other events accurately instead of inventing them. When a host
observes both the network terminal result and the delivery Gate, its emission
order and session `sequence` MUST place the terminal Post before the Gate.

If both events provide `status_code` for the same `operation_id`, the values
MUST match. The Gate reports the original response's protocol status, not a
locally generated delivery error or a later redirect's status.

Redirects and retries remain separate requests with separate `operation_id`
values. This Gate uses the identifiers and original target of the request
that produced this body. A redirect response body that is discarded internally
does not need a delivery Gate; following the redirect still creates a new
request subject to the existing `PreNetworkAccess` rules.

### Proposed request fields

The request keeps the existing flat envelope. It MUST NOT use a generic
`payload` or `context`, or replace `hook_event_name` with `event_type`.

| Member | Requirement | Meaning |
| --- | --- | --- |
| `spec`, `event_id`, `session_id`, `timestamp`, `sequence` | Required | Existing common envelope requirements, including a unique delivery UUID and strictly increasing session sequence. |
| `hook_event_name` | Required | Exactly `BeforeNetworkResponseDelivery`. |
| `prompt_id` | Required | The caller-initiated turn to which the request and delivery belong. |
| `operation_id` | Required | The underlying network request's identifier, retained across its related network and delivery events. |
| `delivery_id` | Required | A nonempty opaque identifier, unique within the session, for one attempt to deliver this body to one consumer. |
| `consumer_id` | Required | The nonempty opaque identifier of the intended consumer within this session. |
| `destination_host`, `destination_port`, `protocol` | Required | This request's original destination and lowercase application protocol, following the existing network-event constraints. |
| `response_body_base64` | Required | The complete body bytes proposed for consumer delivery, encoded as standard padded base64 without whitespace. An empty string represents an observed empty body. |
| `status_code` | Optional | The final status in the declared protocol's namespace, following the existing `PostNetworkAccess` status rules. |
| `response_media_type` | Optional | A nonempty media type when known. This is advisory metadata, not a content-safety guarantee. |
| `extensions` | Optional | Existing reverse-DNS extension namespaces. |

Other optional common envelope members retain their existing meaning. When
the native runtime lacks an operation identifier, an adapter MUST generate
and retain one for the request using the existing
[correlation requirements](../spec/0.1/core.md#security-correlation); it MUST
NOT derive paired-event identity from timing alone. Redelivery or reevaluation
uses a new `event_id` and sequence while retaining the request's operation ID.

A host MUST retain `delivery_id` across handler invocations, event redelivery,
and reevaluation for the same delivery attempt. A new attempt after denial,
or an attempt to release the body to a different consumer, MUST have a new
`delivery_id` and a fresh Gate. `consumer_id` MUST remain stable for an attempt;
an allow for one consumer MUST NOT authorize release to another. The correlated
response's `event_id` binds its decision to these request fields without adding
another response envelope.

### The evaluated body and the delivered body

The bytes decoded from `response_body_base64` MUST be exactly the bytes the
host proposes to release to the consumer. The representation is after the
host's content decoding, such as decompression, and before consumer parsing.
It is not necessarily the compressed bytes received on the wire. In
particular, its decoded length MUST NOT be substituted for the existing
`PostNetworkAccess.bytes_recv`, which counts transmitted body bytes.

Character-set decoding, replacement of invalid character sequences, Unicode
normalization, and structured parsing count as consumer parsing for this
byte-oriented proposal. The Gate MUST precede those operations. A runtime
that exposes only a decoded string or parsed object, without a faithful
earlier byte boundary, MUST declare `partial` or `unavailable`; re-encoding that
value as UTF-8 does not establish what the original consumer-facing bytes were.
This RFC does not standardize the consumer's subsequent parsing behavior.

The producer MUST provide valid base64 that decodes to the complete proposed
body. A hash, a storage path, a prefix such as the first 16 bytes, a truncated
sample, or a redacted substitute cannot replace the required full body. A
handler may choose to inspect only a prefix, but the event does not assert
that this establishes the safety of the remaining content.

A decision applies only to the identified delivery attempt and consumer, and
the body, target, and delivery metadata presented in that event. The host MUST
prevent modification or substitution of the buffer between evaluation and
release. If it changes any security-relevant
part of that proposal, including content decoding or sanitization that changes
the body, it MUST evaluate a new Gate before release. This requirement does
not mandate hashes or signatures; it requires faithful host enforcement.

### Proposed control response

Reuse the correlated Core response envelope: required `spec` and matching
`event_id`, with matching
`hookSpecificOutput.hookEventName: "BeforeNetworkResponseDelivery"`.
`hookSpecificOutput.permissionDecision` uses the existing vocabulary:

| Decision | Proposed effect |
| --- | --- |
| `allow` | Permit delivery of the evaluated body, subject to independent native, sandbox, organization, and approval policies. |
| `deny` | Prevent delivery of the body. The host may return a locally generated refusal or error that does not expose the denied body. |
| `ask` | Keep the body unavailable while the native approval flow resolves the delivery decision. A non-interactive host MUST treat it as `deny`. |
| `defer` | Leave resolution to native approval or policy; it MUST NOT count as approval. |

`permissionDecisionReason` MAY explain the decision without disclosing
protected content or policy details. A structurally valid response without a
decision supplies no hook control result. Top-level `decision: "block"`,
`updatedInput`, `updatedMessages`, and other event-inapplicable control members
MUST have no delivery-control or body-rewriting effect for this event.

This RFC introduces no `transform` or `quarantine` decision enum. `deny`
withholds delivery; any quarantine storage or later release follows a
separately defined native policy. A later attempt by this host to deliver a
previously denied body, whether unchanged or modified, MUST invoke a fresh Gate
with new `delivery_id` and `event_id` values before release. Retention in native
quarantine does not authorize delivery. This RFC does not define reusable
approval grants.

The existing [Core fail-open rule](../spec/0.1/core.md#fail-open-behavior)
remains unchanged. An absent response, invalid JSON or schema, event ID or
event-name mismatch, handler error, or timeout supplies no hook control result;
a host declaring `gate` MUST continue delivery unless an independent native
policy blocks it. A hook failure MUST NOT be reported as an implicit `deny`.
Common async fields do not establish a new remote approval or body-holding
protocol for this Gate.

Consequently, this proposal does not promise that every delivered response
has completed a successful scan. An explicitly configured native policy may
require that stronger guarantee, but it is not the Core default.

### Buffering, privacy, and capability declarations

Adding the proposed event would require each host's capability declaration to
include one of the existing modes for it:

| Mode | Meaning at this boundary |
| --- | --- |
| `gate` | The host observes a complete body before consumer access, supplies it faithfully, and can enforce the applicable delivery decision. |
| `observe` | The host faithfully emits this same before-delivery event, but handler responses do not control delivery. |
| `partial` | The host has a related signal but cannot meet the timing, full-body, correlation, privacy, or control obligations. It MUST NOT emit a normalized Core event for this capability. |
| `unavailable` | The host cannot observe this boundary faithfully. |

Hosts MUST document supported protocols, buffering limits, consuming runtime
paths, and data-handling restrictions for the declared configuration. A host
MUST NOT claim `gate` while silently falling back to incremental or uninspected
delivery for oversized bodies or unsupported paths. It may reject such delivery
under a separately declared native resource policy, or declare that the
configuration cannot faithfully support the Gate. A rejected buffer allocation
or decoding failure is a native resource/transport failure, not a fabricated
complete-body event or handler denial. Once a valid event is submitted, a
handler's size-limit error still follows the Core fail-open rule.

Bodies can contain credentials, source code, personal data, or attacker-controlled
content. The host MUST apply its disclosure policy before selecting and invoking
a handler. Base64 is a transport representation, not redaction or encryption.
When the full body cannot be disclosed safely, the host must use an authorized
handler that can process it, such as a local handler, or declare the capability
limitation. It MUST NOT replace sensitive bytes and claim it evaluated the
original full body. A handler MUST treat the body as untrusted data, not as
instructions or executable content.

### Recording a delivery denial

A host SHOULD record the event, operation, delivery, consumer, and turn
identifiers, the handler decision or failure class, and the actual delivery
outcome in its diagnostics.
It SHOULD omit the response body and sensitive metadata from those records.
This RFC does not prescribe a ledger format or add a terminal delivery event.
An `allow` response alone is not evidence that delivery ultimately occurred.

A handler denial MUST NOT fabricate a `PermissionDenied` event. Existing
permission events may be used only when the native approval boundary and all
their required fields and correlation rules are satisfied. Likewise, denial
does not create a second `PostNetworkAccess` or change its terminal outcome.

## Illustrative exchange

These examples describe the **candidate contract**. The new name is
intentionally unsupported by the current 0.1 schemas. The body below is a
complete four-byte synthetic response containing an ELF marker, not a
truncated executable. The example policy prohibits such downloads; detecting
an ELF marker alone does not establish that a real file is malicious.

The network request completed successfully:

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "018f6c3a-9214-7abc-9f12-34567890ab01",
  "hook_event_name": "PostNetworkAccess",
  "session_id": "session-42",
  "timestamp": "2026-09-15T02:00:00Z",
  "sequence": 50,
  "prompt_id": "prompt-7",
  "operation_id": "network-request-9",
  "destination_host": "downloads.example.com",
  "destination_port": 443,
  "protocol": "https",
  "outcome": "success",
  "status_code": 200,
  "bytes_recv": 4
}
```

The host still holds the body, and asks about its delivery:

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "018f6c3a-9214-7abc-9f12-34567890ab02",
  "hook_event_name": "BeforeNetworkResponseDelivery",
  "session_id": "session-42",
  "timestamp": "2026-09-15T02:00:00Z",
  "sequence": 51,
  "prompt_id": "prompt-7",
  "operation_id": "network-request-9",
  "delivery_id": "body-delivery-1",
  "consumer_id": "consumer-agent-42",
  "destination_host": "downloads.example.com",
  "destination_port": 443,
  "protocol": "https",
  "status_code": 200,
  "response_media_type": "application/octet-stream",
  "response_body_base64": "f0VMRg=="
}
```

The handler denies delivery, without rewriting the earlier network result:

```json
{
  "spec": "agent-hooks/0.1",
  "event_id": "018f6c3a-9214-7abc-9f12-34567890ab02",
  "hookSpecificOutput": {
    "hookEventName": "BeforeNetworkResponseDelivery",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Executable downloads are not permitted by this policy."
  }
}
```

The host withholds the four body bytes and may return a safe local error or
retain the body in a native quarantine. `PostNetworkAccess.outcome` remains
`success`. Consumers must not interpret that network result as authorization
to release the body.

## Compatibility impact

The proposed change adds a nineteenth Core event in a future revision of the
unaccepted 0.1 draft; it does not rename or change the control semantics of any
existing event. Current schemas reject the proposed name, and existing handlers
must not receive it until explicitly configured for an adopted revision.
Keeping `spec: "agent-hooks/0.1"` while this draft remains unaccepted would not
itself establish compatibility, as already documented by
[RFC 0004](./0004-standard-lifecycle-events.md#compatibility-impact).

If 0.1 is accepted before this proposal is decided, the versioning plan must
be revisited through the RFC process rather than silently changing a published
contract. There is no automatic handler discovery or negotiation in this RFC.

Existing native quarantine code can remain in a vendor integration, but must
identify its current behavior as native or proposed. It must not attribute
that enforcement to a Core `PostNetworkAccess` response. No automatic Claude
Code, NeMo Relay, or other host mapping is claimed; implementations must
demonstrate a faithful before-delivery boundary.

## Security and privacy impact

The Gate adds a portable point for preventing selected response bodies from
reaching an agent, provided the host controls the full buffer. It cannot undo
request-side disclosure or a remote action. It also cannot retract previously
released streaming chunks or guarantee semantic safety after parsing.

Complete-body buffering and base64 increase memory, copying, and handler
payload costs. Hosts need explicit resource and retention limits, authorized
inspection endpoints, least-privilege access, and diagnostics that do not
persist sensitive bodies. A quarantine must not itself become a readable
backdoor to denied content. These are host responsibilities, not a required
enterprise service or a security certification supplied by this RFC.

Default fail-open, native-policy precedence, faithful byte binding, and honest
capability declarations are required together. A deployment requiring all
content to be successfully scanned before delivery needs a separate native
policy covering handler failures and resource limits.

## Alternatives considered

| Alternative | Trade-off |
| --- | --- |
| Make `PostNetworkAccess` a Gate | Reuses a name, but changes an existing Observe contract, combines network outcome with delivery authorization, and cannot describe early-chunk inspection as a terminal result. A separate boundary preserves both meanings. |
| Add only a vendor event | Enables experimentation under the existing extension policy and remains appropriate before adoption. It does not provide a shared delivery contract across vendors. |
| Approve each streaming chunk | Reduces buffering latency, but introduces ordering, cross-chunk inspection, cancellation, and already-released-content semantics. It needs a separate proposal. |
| Pass only a hash, prefix, or body reference | Reduces payload size, but does not give every handler the complete evaluated representation. Reference resolution, access, and lifetime would need an additional contract. |
| Add body rewriting or a `quarantine` enum | Expands policy and storage semantics beyond withholding delivery. The existing `deny` decision is sufficient for this proposal. |

## Follow-up implementation and acceptance criteria

After acceptance, a follow-up PR must update the canonical event registry,
Core response and correlation rules, security and adapter guidance, root and
published website schemas, fixtures, event counts, capability declarations,
and examples together. It must add the new request variant and both schemas'
event-name enumerations without relaxing existing request or response rules.

Implementations and conformance guidance must cover at least the following
cases. These are acceptance criteria, not claims of runtime tests executed by
this proposal PR:

| Case | Required result |
| --- | --- |
| Complete text, binary, and empty bodies | Encode and expose the complete intended representation; a valid allow releases exactly those bytes when native policy permits. |
| Valid deny | No body bytes reach the consumer, including via a readable temporary file or side channel owned by the adapter. |
| Complete HTTP 403/500 body denied | Network Post remains `success`; delivery is separately denied. |
| Both network Post and delivery Gate include a status | Their status codes match for the same operation; a local refusal cannot replace that status. |
| Incomplete transfer | Report the actual network failure/interruption where supported; do not fabricate a complete-body Gate. |
| Before-delivery observation without enforcement | Declare `observe`; do not report successful blocking by this hook. |
| Previously released streaming chunk | Do not claim the complete-body Gate or emit a normalized event under a `partial` capability. |
| Redacted, truncated, prefix-only, invalid-base64, or hash-only input | Do not treat it as a faithful complete-body event. |
| Changed body or security-relevant metadata | Invalidate the prior decision and evaluate again before release. |
| Attempt to release a previously denied body | Invoke a fresh Gate with new delivery and event IDs, even if the body is unchanged. |
| Same body offered to a different consumer | Use that consumer's identity and a new delivery attempt; do not reuse the first consumer's allow. |
| Handler invocation or reevaluation for the same attempt | Preserve delivery, consumer, and operation identities while assigning a fresh event ID. |
| Runtime exposes only a decoded string or parsed object | Declare partial/unavailable; do not re-encode it and claim the required byte boundary. |
| Redirect, retry, or redelivery | Preserve the specified request correlation; use distinct operation IDs for new requests and distinct event IDs for deliveries. |
| Mismatched response event ID/name, malformed response, timeout, or error | No hook control result; follow Core fail-open and record a minimal diagnostic. |
| Native policy denies despite handler allow | Keep delivery blocked. |
| Native `ask` or `defer` | Retain the buffer while required native approval resolves; never treat defer as approval or assume consent on a non-interactive host. |
| Buffer limits or an unsupported delivery path | Apply the declared native resource policy or capability limitation; do not silently bypass a claimed Gate. |
| Denial auditing | Do not emit an extra network terminal event, rewrite its outcome, or invent a native permission denial. |

JSON Schema validation alone cannot establish that a host withheld bytes,
preserved the evaluated buffer, applied the correct event-specific response,
or maintained correlation across events. The follow-up must distinguish
structural fixture checks from host semantic and integration tests.

## References

- [RFC 0001: Agent Hook 0.1 Core Event Contract](./0001-agent-hook-core-event-contract.md).
- [RFC 0004: Standard network, memory, and configuration lifecycle events](./0004-standard-lifecycle-events.md).
- [Core protocol](../spec/0.1/core.md).
- [Event registry](../spec/0.1/events.md).
- [Extension policy](../spec/0.1/extensions.md).
- [Security considerations](../spec/0.1/security.md).
- [Related enterprise integration proposal, PR #1](https://github.com/trendmicro/agent-hook-unity/pull/1).

The receive-side inspection and quarantine use case arose during review of an
enterprise governance integration. This RFC proposes the shared boundary and
does not claim that any vendor has accepted, co-authored, or implemented it.

## Decision record

Pending. No formal review window, maintainer votes, or acceptance are recorded.
The prerequisite Discussion and at least 14 calendar days of public review
must be completed before a decision under repository governance. This draft
does not supersede RFC 0004 or the remaining enterprise work in PR #1.
