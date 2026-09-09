---
sidebar_position: 4
---

# Conformance

The initial scaffold does not contain a protocol or conformance suite. As the
specification develops, accepted schemas will use JSON Schema Draft 2020-12 and
will be paired with valid and invalid JSON fixtures.

Repository validation will require each schema to declare a stable identifier
and title, valid examples to pass, and invalid examples to fail. This provides a
small, machine-checked foundation before an executable certification harness is
needed.
