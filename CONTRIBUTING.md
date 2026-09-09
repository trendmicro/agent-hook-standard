# Contributing to Agent Hook Spec

Thank you for your interest in improving the Agent Hook Spec. We welcome
documentation corrections, schema and example improvements, feature proposals,
and fixes.

## Before you contribute

- Keep contributions focused, well explained, and consistent with the existing
  specification and examples.
- Do not include secrets, credentials, access keys, or proprietary product
  code.
- If your change adds or updates third-party material, make sure its license is
  compatible with this repository.

## Discussing ideas and reporting issues

Use [GitHub Discussions](https://github.com/trendmicro/agent-hook-standard/discussions)
for questions, ideas, use cases, and proposed changes to the Agent Hook Spec.
Start a discussion before drafting an RFC so the community can help shape the
proposal.

Use GitHub Issues only for reproducible repository defects, such as a broken
link, invalid fixture, build failure, or problem with this website. Include
enough detail for maintainers to understand and reproduce the problem. Helpful
details include:

- The affected file, section, schema field, or example.
- What you expected and what you observed.
- A concise proposed correction or use case, where applicable.

For substantial changes to the protocol, schema, or semantics, follow the RFC
process in [GOVERNANCE.md](GOVERNANCE.md). A formal RFC pull request must link
to its prior GitHub Discussion.

## Contributing changes

1. Fork the repository and clone your fork locally.
2. Create a descriptive branch for one feature, fix, or documentation update.
3. Make the change. Keep JSON examples valid and update related schema,
   documentation, and comparison files when needed.
4. Install dependencies and run the validation suite:

   ```sh
   npm ci
   npm run validate
   npm run build
   ```

5. Commit with a clear, meaningful message.
6. Push the branch to your fork.
7. Open a pull request against this repository. Explain what changed, why it is
   needed, and how you validated it. Link the related Discussion, Issue, or RFC
   when one exists.

## Pull request expectations

- Keep pull requests small and focused where practical.
- Ensure all checks pass before requesting review.
- Include documentation and examples for user-visible schema changes.
- Respond to review feedback and update the pull request as needed.
- Be respectful and constructive in all project interactions.

## Security concerns

Do not report security-sensitive issues in a public GitHub issue. Follow this
repository's security policy when one is available, or contact a maintainer
privately.

## Contact

For questions, use the GitHub support channel or contact
`alloftrendgithubenterpriseadmin@trendmicro.com`.

Thank you for helping make this specification clearer, more reliable, and more
useful.
