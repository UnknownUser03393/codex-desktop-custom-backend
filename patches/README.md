# Patches

## `exec-policy-allow-unmatched.patch`

Changes `codex-rs/core/src/exec_policy.rs::render_decision_for_unmatched_command_for_platform`
to return `Decision::Allow` for commands that match **no explicit exec policy rule**.

The original function combined the dangerous-command heuristic with the approval
policy and filesystem sandbox shape, returning `Forbidden` or `Prompt` in several
cases. After this patch, unmatched commands are always allowed; explicit rules in
`~/.codex/rules/*.rules` still take precedence.

Apply against the tag matching your Codex Desktop build (verified with
`v0.171.0-alpha.13`):

```bash
git apply exec-policy-allow-unmatched.patch
```

## Migration line endings (required)

`sqlx` hashes the raw bytes of each migration file and records the SHA-384 in
`_sqlx_migrations`. The official Windows release embeds `codex-rs/state/**/*.sql`
with **CRLF**. A checkout with **LF** produces different checksums for all 72
migrations, and the app-server refuses to open an existing profile:

```
failed to migrate state DB at ...\state_5.sqlite:
migration 1 was previously applied but has been modified
```

Keep the files byte-identical to the release before building:

```
codex-rs/state/**/*.sql text eol=crlf
```

That rule is included in `.gitattributes`. Do not let an editor normalize these
files to LF.

## Verification performed

- Both the app-server and exec-server processes were observed running from the
  custom directory.
- In a Desktop chat, `exec_command` with `rm -rf *` reached PowerShell
  (`exit_code: 1`, `A parameter cannot be found that matches parameter name 'rf'.`)
  with **no policy rejection or approval request**.
- `Remove-Item -Recurse -Force *` in a dedicated test directory exited `0` and
  removed all test files.
