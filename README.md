# Codex Desktop Custom Backend

Run OpenAI **Codex Desktop** (Windows MSIX/AppX) against a **self-built `codex-cli`**
instead of the `codex.exe` bundled in the package.

This repo documents the mechanism, provides a minimal source patch, and includes
helper scripts for install / verification / rollback.

---

## Why replacing the cached binary doesn't work

On Windows, Codex Desktop relocates its runtime executables on every launch:

- Source: `...\WindowsApps\OpenAI.Codex_<version>_x64__<publisher>\app\resources\codex.exe`
- Destination: `%LOCALAPPDATA%\OpenAI\Codex\bin\<16-hex-hash>\codex.exe`
  (the directory name is derived from SHA-256 digests of `codex.exe` and its siblings)
- Before launching, the Electron main process compares the destination files by
  **size + SHA-256**. Any mismatch causes the whole directory to be deleted and
  re-copied from the package.

So editing the cache is futile — it is restored on the next start.

Reference: `app.asar` → `.vite/build/app-server-host.js`
(`bundled_executable_relocation_failed`, `sourceKind:"windowsapps"`,
`R()` / `v()` helpers).

## The stable override

The same resolver honors `CODEX_CLI_PATH`:

```js
function ea(){ let e = process.env.CODEX_CLI_PATH; ... }
// → { executablePath, args, source: "override" }
```

With an absolute path in `CODEX_CLI_PATH`, Codex Desktop skips the cache
validation/copy entirely and spawns `app-server` / `exec-server` from your binary.

Set it as a **user** environment variable and broadcast `WM_SETTINGCHANGE`; new
processes launched by Explorer inherit it. Restart Codex Desktop afterwards.

```powershell
[Environment]::SetEnvironmentVariable('CODEX_CLI_PATH', 'D:\Tools\CodexCustom\codex.exe', 'User')
# broadcast WM_SETTINGCHANGE (tools\set_user_env_broadcast.ps1 does this)
```

## Critical: sqlx migration checksums and CRLF

`sqlx` computes a SHA-384 over the **raw bytes** of every migration file and stores
it in `_sqlx_migrations`. The official Windows release embeds SQL migrations with
**CRLF** line endings. If you build from a checkout with **LF**, every checksum
differs and the app-server refuses to open an existing profile:

```
failed to migrate state DB at ...\state_5.sqlite:
migration 1 was previously applied but has been modified
```

Fix: keep `codex-rs/state/**/*.sql` as CRLF before building.
This repo's `.gitattributes` enforces it:

```
codex-rs/state/**/*.sql text eol=crlf
```

Do not let editors normalize these files to LF.

## Build

```bash
git clone https://github.com/openai/codex.git
cd codex
git checkout v0.171.0-alpha.13        # or the tag matching your Desktop build
git apply /path/to/exec-policy-allow-unmatched.patch
# ensure CRLF migrations (see .gitattributes)
git add .gitattributes
cargo build --release -p codex-cli --bin codex --offline
```

Output: `codex-rs/target/release/codex.exe`.

## Install

1. Create a stable directory, e.g. `D:\Tools\CodexCustom\`.
2. Put the built `codex.exe` there.
3. Copy the original signed helper executables from the package's `app\resources\`
   next to it (they are looked up via `current_exe().parent()`):

   - `codex-command-runner.exe`
   - `codex-windows-sandbox-setup.exe`
   - `codex-windows-sandbox-service.exe`
   - `codex-code-mode-host.exe`
   - `rg.exe`

4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_backend.ps1 `
  -BuiltExe D:\codex\codex-rs\target\release\codex.exe `
  -TargetDir D:\Tools\CodexCustom
```

5. Quit Codex Desktop completely, then launch it again.

## Verify

```powershell
Get-CimInstance Win32_Process -Filter "Name='codex.exe'" |
  Select-Object ProcessId,ParentProcessId,ExecutablePath
Get-FileHash D:\Tools\CodexCustom\codex.exe -Algorithm SHA256
```

Expected: the `app-server` and `exec-server` processes point at your custom
directory. The packaged cache under `%LOCALAPPDATA%\OpenAI\Codex\bin\` remains
untouched.

## Rollback

```powershell
powershell -ExecutionPolicy Bypass -File tools\restore_backend.ps1
```

This deletes the user-level `CODEX_CLI_PATH`. Restart Desktop; it will use the
packaged original again. The package and cache were never modified.

## Patch

`patches/exec-policy-allow-unmatched.patch` changes
`codex-rs/core/src/exec_policy.rs::render_decision_for_unmatched_command_for_platform`
to return `Decision::Allow` for commands that match **no explicit exec policy rule**.

Effect: the dangerous-command heuristic no longer blocks/prompts unmatched
commands. Commands matched by explicit `deny` / `ask` rules in `~/.codex/rules/*.rules`
still follow those rules.

## Security warning

- This patch disables a security heuristic. Use it only on a machine you control.
- `%USERPROFILE%\.codex\auth.json` contains ChatGPT credentials, and
  `sessions/`, `state_*.sqlite`, `logs_*.sqlite` contain private chat data.
  **Never commit them.** The included `.gitignore` excludes them.
- Do not copy the extracted `app.asar` contents into a public repo; they are
  proprietary application code.

## Contents

| Path | Purpose |
|---|---|
| `patches/exec-policy-allow-unmatched.patch` | Minimal functional patch |
| `patches/README.md` | CRLF / migration notes |
| `tools/install_backend.ps1` | Copy binary + set env |
| `tools/restore_backend.ps1` | Remove env (rollback) |
| `tools/set_user_env_broadcast.ps1` | Set/remove user env and broadcast |
| `tools/appserver_probe.py` | JSON-RPC `initialize` + `command/exec` probe |
| `tools/appserver_threads.py` | `thread/list` probe |
| `tools/asar_tool.py` | Parse/extract/search an Electron `app.asar` |
| `REPORT.md` | Full investigation and verification report |

## License

This repository uses mixed licensing:

- Original scripts and documentation: **MIT** (see `LICENSE`).
- `patches/exec-policy-allow-unmatched.patch` applies to the OpenAI Codex CLI,
  which is **Apache-2.0**. The copy of that license is in
  `LICENSES/Apache-2.0.txt`; the upstream NOTICE terms are reproduced in
  `NOTICE`. No upstream source tree is bundled in this repository.

If you redistribute a Codex source tree or binary, the Apache-2.0 terms and the
upstream NOTICE apply to those parts.
