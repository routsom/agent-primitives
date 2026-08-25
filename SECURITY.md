# Security policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities. Instead, use
GitHub's private vulnerability reporting: go to the repository's **Security** tab →
**Report a vulnerability**.

Include:

- A description of the issue and its potential impact
- Steps to reproduce (a minimal example is ideal)
- Which runtime is affected (`typescript/`, `python/`, or both) and version/commit

We aim to acknowledge reports within 5 business days.

## Scope and trust-boundary notes specific to this project

This boilerplate runs LLM agents that call tools, other agents (via A2A), and MCP servers.
The threat model in `reference/multi-agent-architecture-notes.md` §7 applies directly:

- **Tool outputs, other agents' outputs, and inbound A2A tasks are all untrusted input.**
  Prompt injection can arrive via any of these paths and should be assumed possible when
  reviewing changes to `harness/`, `mcp/`, or `a2a/`.
- **"Another agent said so" is never an authorization boundary.** Every delegated
  instruction, including from a trusted-looking source, must pass through the same harness
  validation (auth, scope, confirmation gates) as a direct user instruction. Report any code
  path that bypasses this as a security issue, not a feature request.
- **Least privilege is enforced per agent role.** A subagent should never hold a tool the
  lead agent has if that role doesn't need it. Report any role that appears
  over-privileged relative to its stated objective.

## Supported versions

This is a boilerplate, not a versioned library with a long-term support policy — security
fixes land on `main`. Pin to a commit and re-sync deliberately rather than expecting
backported patches to older tags.
