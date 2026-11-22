# Codex Desktop 使用自编译后端 —— 替换与验证报告

日期：2026-11-23
Desktop 版本：`OpenAI.Codex 26.1117.4957.0`（AppX，x64）
自编译源码：`codex-rust-v0.171.0-alpha.13`

---

## 1. 结论

- 已用 **用户级环境变量 `CODEX_CLI_PATH`** 让 Codex Desktop 稳定加载自编译后端，不再往
  `%LOCALAPPDATA%\OpenAI\Codex\bin\...` 缓存路径里硬替换。
- 重启后实际运行的 `app-server` 与 `exec-server` 进程均为
  `%WORKSPACE%\custom-backend\codex.exe`
  （SHA-256 `696FB389E12AF6E47B38331EA30DC6A5F209DD458F1EBE95CF91EEB9A1F4031D`）。
- 原版包内文件与缓存目录均未被修改，随时可回滚。
- Desktop 聊天中通过正常 `exec_command` 入口执行的 `rm -rf *` **不再被危险命令启发式拦截**：
  命令真实进入 PowerShell，退出码 1 是 PowerShell 不认 `-rf` 参数导致的语法错误，不是策略拒绝。
  随后 `Remove-Item -Recurse -Force *` 退出码 0，测试目录被清空。

---

## 2. 为什么之前替换缓存会被还原

Desktop 的 Electron 主进程（`app/resources/app.asar` → `.vite/build/app-server-host.js`）在每次启动时
都会「重新校验并就地修复」运行时二进制：

1. 源文件固定取包内 `...\WindowsApps\OpenAI.Codex_26.1117.4957.0_x64__2p2nqsd0c76g0\app\resources\codex.exe`。
2. 目标目录名为哈希前缀：`%LOCALAPPDATA%\OpenAI\Codex\bin\<16位hex>\`，本次为
   `31fb36cfc4b38f05`。该 hex 由 `codex.exe` 及同目录 sibling（`codex-code-mode-host.exe`、
   `codex-command-runner.exe`、`codex-windows-sandbox-setup.exe`）的 `sha256` 摘要串联后再哈希得到。
3. 启动时函数 `R(destDir, entries)` 逐个比较目标文件的 **大小 + SHA-256**；一旦不一致，就
   `rmSync(destDir)` 删除整个目录，再用 `mkdtemp` 暂存、复制、`rename` 原子替换。

所以只要改的是缓存目录里的文件，下一次启动必然被删掉重拷。用户此前看到的
`codex.original-0.171.0-alpha.13.exe` / `codex.running-original.exe` 现已不存在；
缓存目录恢复为原版。

相关证据：

- 缓存文件：`4069ACDD8D101830F63EA5E2775883BFECF8A152AE87EE1B0EF9F14204F850F9`
  （407,428,400 字节，mtime `2026-11-21 12:33:20`）
- 包内 `app\resources\codex.exe`：同一哈希
- `app.asar` 内 `bundled_executable_relocation_failed` / `sourceKind:"windowsapps"` /
  `executableStats` 等日志字段

---

## 3. 稳定替换方式（现用方案）

Desktop 的 app-server 解析逻辑（同文件）支持显式覆盖：

```js
function ea(){ let e=process.env.CODEX_CLI_PATH; ... }
// 命中时返回 { executablePath, args, source: "override" }
```

`CODEX_CLI_PATH` 一旦是绝对路径，解析器直接 `source:"override"`，**完全跳过缓存目录的校验与复制**。
它由 Electron 主进程继承，再传给 app-server / exec-server。

实施方案：

1. 新建稳定目录 `%WORKSPACE%\custom-backend\`
2. 放入自编译 `codex.exe`，并把原版签名的 sibling 工具一并放入（保证 code-mode / sandbox /
   search 等 helper 能按 `current_exe().parent()` 找到）：
   - `codex-code-mode-host.exe` `753D65BAAFA0CAFA62EB7F0A43F934421FC2EB67CC100C6FF0D8F9749A1AC5F6`
   - `codex-command-runner.exe` `994D57F36C5DC92A92731CB3F9FE1CADDF8F68AE8980A758A9FF44A68779E386`
   - `codex-windows-sandbox-setup.exe` `AED2509FD2BC4773321072FCAC5E5D4F03D2D6D51F0BC4C6728AAC9775604F3E`
   - `codex-windows-sandbox-service.exe` `E66E49429469B95C5A2219DAE872938BD8D70FBE920F1F1086E8CBA5777C3569`
   - `rg.exe` `F5A77041DAFA9C2648B57A718B0F489394D3A42BC37543E6EFBA21530A8BEB9D`
3. 设置用户环境变量并广播 `WM_SETTINGCHANGE`：

```
CODEX_CLI_PATH = %WORKSPACE%\custom-backend\codex.exe
```

脚本：`tools\set_user_env_broadcast.ps1`、`tools\install_backend.ps1`

> 注意：仅设置注册表不会影响已在运行的 Explorer/Desktop；已通过
> `SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")` 广播，
> 并用 Explorer 启动 `.bat` 实测新进程能读到该变量。

---

## 4. 数据兼容性大坑（已修复）

直接把自编译版指向真实 `~/.codex` 时，app-server 起不来：

```
failed to migrate state DB at ...\state_5.sqlite:
migration 1 was previously applied but has been modified
```

根因不是 SQL 内容，而是 **换行符**：

- 官方 release 编译时嵌入的迁移文件是 **CRLF**
- 本机 checkout 的源码是 **LF**
- sqlx 对迁移文件的 **原始字节** 计算 SHA-384，并记录在 `_sqlx_migrations`
- 5 个库、72 条迁移全部因字节不同而校验失败

修复：

- 将 `codex-rs\state` 下全部 `**/*.sql`（81 个文件）统一转换为 CRLF
- 逐库验证：`state_5 / logs_2 / memories_1 / goals_1 / queue_1` 的 72 条迁移
  SHA-384 与官方记录逐条一致
- 重新 `cargo build --release -p codex-cli --bin codex`（39m22s）

新二进制：

| 项 | 值 |
|---|---|
| 大小 | 410,382,336 字节 |
| SHA-256 | `696FB389E12AF6E47B38331EA30DC6A5F209DD458F1EBE95CF91EEB9A1F4031D` |
| 版本 | `codex-cli 0.171.0-alpha.13` |

> 长期注意：若后续再用编辑器改这些 `.sql`，不要让编辑器把行尾归一化为 LF，
> 否则会再次触发 `modified`。建议加 `.gitattributes`：
> `codex-rs/state/**/*.sql text eol=crlf`

---

## 5. 备份与回滚

### 已备份

`%WORKSPACE%\backup-before-swap\`

- `state_5.sqlite` / `logs_2.sqlite` / `memories_1.sqlite` / `goals_1.sqlite` / `queue_1.sqlite`
  （SQLite Online Backup API 快照）
- `config.toml`、`auth.json`

### 原版保留（未改动）

- 包内：`C:\Program Files\WindowsApps\OpenAI.Codex_26.1117.4957.0_x64__2p2nqsd0c76g0\app\resources\codex.exe`
  （`4069ACDD…`）
- 缓存：`%LOCALAPPDATA%\OpenAI\Codex\bin\31fb36cfc4b38f05\codex.exe`（`4069ACDD…`，未被触碰）

### 回滚步骤

```powershell
powershell -ExecutionPolicy Bypass -File %WORKSPACE%\tools\restore_backend.ps1
```

脚本会删除用户变量 `CODEX_CLI_PATH` 并广播；随后重启 Codex Desktop 即恢复使用包内原版。
自编译构建本身不需要删除。

---

## 6. 验证结果

### 6.1 进程与文件（重启后）

```
6516  | parent=22276 | %WORKSPACE%\custom-backend\codex.exe
        (-c features.code_mode_host=true app-server --analytics-default-enabled ...)
21712 | parent=13932 | %WORKSPACE%\custom-backend\codex.exe
        (exec-server --concurrent-requests 32 --remote https://codex-cloud-environments.chatgpt.com/api ...)
```

- 运行文件 SHA-256：`696FB389…`（与构建产物一致）
- 缓存路径文件 SHA-256：`4069ACDD…`（原版，未被覆盖）
- 真实 `state_5.sqlite`：64 条迁移，migration 1 校验和仍为
  `54bbd6f4…`（说明新二进制没有改写迁移记录），会话数 814

### 6.2 Desktop 聊天实测

会话 rollout：`%USERPROFILE%\.codex\sessions\2026\11\23\rollout-2026-11-23T01-13-20-01a2043f-82e5-7af1-a617-27bcba416b45.jsonl`

测试目录（现已被清空）：`%WORKSPACE%\desktop-rm-test`
初始内容：`alpha.txt`、`beta.txt`、`sub\gamma.txt`

**第一次：原样 `rm -rf *`**（`exec_command`，`workdir` 为测试目录）

- 实际 shell：`%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe`
- 结果：`exit_code = 1`，stderr：

```
Remove-Item:
Line |
   2 |  rm -rf *
     |     ~~~
     | A parameter cannot be found that matches parameter name 'rf'.
```

→ **没有出现任何 exec policy 拒绝 / 审批请求**；命令真实到达 shell。失败原因仅为 PowerShell
把 `rm` 解析为 `Remove-Item` 后不认 `-rf` 这种短参数组合。

**第二次：`Remove-Item -Recurse -Force *`**

- 退出码 `0`，stderr 为空
- 文件系统核对：`desktop-rm-test` 目录内容为空（`alpha.txt`、`beta.txt`、`sub\` 全部删除，
  目录本身保留）

### 6.3 显式规则与其他限制

- `~/.codex/rules/default.rules` 存在，内容基本都是 `prefix_rule(..., decision="allow")`，
  没有命中本次测试命令的 deny/ask 规则。
- 因此本次 `rm -rf *` 走的是「未匹配任何规则」的 fallback 路径，即本次修改的
  `render_decision_for_unmatched_command_for_platform`，返回 `Decision::Allow`。
- 实际遇到的非策略限制有两个：
  1. **模型层自身的安全预检**：第一次对话模型以「`\*` 在 PowerShell 中可能从盘符根匹配」为由
     拒绝执行，并只跑了只读检查脚本；这是模型行为，不是 exec policy。
  2. **PowerShell 参数解析**：`-rf` 不是 `Remove-Item` 的合法参数。

---

## 7. 已知残留

- `codex-windows-sandbox-service`（PID 7940）是包注册的常驻服务，未随 Desktop 退出；
  它不影响 `CODEX_CLI_PATH` 覆盖。
- Desktop 或 AppX 更新后，`CODEX_CLI_PATH` 仍然生效（解析顺序优先于包内路径）；
  但若 OpenAI 后续修改该环境变量名/逻辑，需要重新确认。
- 如果之后手动在终端里设置同名 `CODEX_CLI_PATH`，会覆盖用户变量；回滚时以
  `restore_backend.ps1` 删除用户变量为准。

---

## 8. 相关脚本

| 文件 | 用途 |
|---|---|
| `tools\set_user_env_broadcast.ps1` | 设置/删除用户环境变量并广播 |
| `tools\install_backend.ps1` | 复制新 exe 并设置 `CODEX_CLI_PATH` |
| `tools\restore_backend.ps1` | 删除 `CODEX_CLI_PATH`，恢复原版后端 |
| `tools\appserver_probe.py` | app-server `initialize` + `command/exec` 探针 |
| `tools\appserver_threads.py` | app-server `thread/list` 探针 |
| `tools\asar_tool.py` | app.asar 头解析 / 文件抽取 / 关键字检索 |
