---
sidebar_position: 4
---

import Link from '@docusaurus/Link';

# Conformance

Agent Hook 0.1 defines three conformance roles: event producer, handler, and
adapter. The draft's normative requirements and role definitions are in the
<Link to="/specification/0.1/core">core protocol</Link>.

The repository validates the 0.1 event and response JSON Schemas against
focused valid and invalid fixtures. Each schema uses JSON Schema Draft 2020-12,
declares a stable identifier and title, and is published at its versioned schema
URL. Run the following checks before requesting review:

```sh
npm run validate
npm run build
```

Schema validation proves document shape, not complete runtime behavior. An
adapter review must additionally verify correct event mapping, `event_id`
correlation, decision handling, and the required fail-open behavior for invalid,
missing, timed-out, or errored handler responses.

For the network and memory event pairs, verify that concurrent operations at
the same destination or memory key retain distinct `operation_id` values, and
that each terminal result retains its operation's identity. Network redirects
and retries require separate request boundaries. `PreConfigChange` denial
must prevent the change before it takes effect. An Observe callback cannot
claim any of these preventive effects.

The revised draft adds five event names. Existing 0.1 schemas do not recognize
them; upgrade schemas and capability declarations and configure compatible
handlers before delivery. Native `ask` still uses the host's approval flow;
no asynchronous approval profile is required.
