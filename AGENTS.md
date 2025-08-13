# QuantConnect MCP — Agents Guide

A concise contract for MCP clients (e.g., Codex CLI) connecting to the QuantConnect MCP server.
Focus: full method enumeration, stateful returns captured in-session, and sensible defaults so users aren’t asked for IDs you can derive.

## 1) Operating Principles

- **Discoverability-first**: Treat all listed methods below as available tools. If more appear later, apply the same rules in §3–§5 without special casing.
- **Stateful by default**: Every method return is harvested for IDs and handles; store them in the session context for reuse.
- **Don’t pester for IDs**: When a method parameter is omitted, resolve it from context (see §4) or derive it (e.g., by name lookup).
- **Explicit overrides**: If the user supplies an ID/arg, it wins over context.
- **Chain responsibly**: Create → Compile → Backtest and Live workflows should auto-chain using captured IDs.
- **Reset narrowly**: Creating/deleting a top-level resource (e.g., a new project) refreshes only the relevant slice of context (see §4.4).

## 2) Method Registry
Use these method names exactly. Do not expose or rely on REST paths.

### Account
- `read_account`

### Projects
- `create_project`
- `read_project` (single)
- `list_projects` (all)
- `update_project`
- `delete_project`

### Project Collaboration
- `create_project_collaborator`
- `read_project_collaborators`
- `update_project_collaborator`
- `delete_project_collaborator`

### Project Nodes
- `read_project_nodes`
- `update_project_nodes`

### Compile
- `create_compile`
- `read_compile`

### Files
- `create_file`
- `read_file`
- `update_file_name`
- `update_file_contents`
- `delete_file`

### Backtests
- `create_backtest`
- `read_backtest`
- `list_backtests`
- `read_backtest_chart`
- `read_backtest_orders`
- `read_backtest_insights`
- `update_backtest`
- `delete_backtest`

### Optimizations
- `estimate_optimization_time`
- `create_optimization`
- `read_optimization`
- `list_optimizations`
- `update_optimization`
- `abort_optimization`
- `delete_optimization`

### Live Trading
- `authorize_connection`
- `create_live_algorithm`
- `read_live_algorithm`
- `list_live_algorithms`
- `read_live_chart`
- `read_live_logs`
- `read_live_portfolio`
- `read_live_orders`
- `read_live_insights`
- `stop_live_algorithm`
- `liquidate_live_algorithm`

### Live Commands
- `create_live_command`
- `broadcast_live_command`

### Object Store
- `upload_object`
- `read_object_properties`
- `read_object_store_file_job_id`
- `read_object_store_file_download_url`
- `list_object_store_files`
- `delete_object`

### LEAN Versions
- `read_lean_versions`

### AI Helpers
- `check_initialization_errors`
- `complete_code`
- `enhance_error_message`
- `update_code_to_pep8`
- `check_syntax`
- `search_quantconnect`

### MCP Server Metadata
- `read_mcp_server_version` (local server version)

## 3) Universal State Capture Rules

On every method response:

- **Harvest IDs/keys**
  - Any field named *Id or *ID (e.g., `projectId`, `compileId`, `backtestId`, `optimizationId`, `algorithmId`, `deployId`, `commandId`).
  - Common non-ID handles: names, symbols, file paths, object keys.
- **Namespace & store**
  - Map known IDs into namespaced context:
    - `projectId` → `context.project.id`
    - `compileId` → `context.compile.id`
    - `backtestId` → `context.backtest.id`
    - `optimizationId` → `context.optimization.id`
    - `algorithmId`/`deployId` → `context.live.id`
    - `commandId` → `context.live.command.id`
  - Unknown `*Id` keys: store under `context.ids.<key>` and mirror into `context.last.id` for quick reuse.
- **Arrays & lists**
  - For list responses, keep `context.recent.<domain> = [ ... ]` (most recent first).
  - If a list is clearly ordered by recency or creation time, set `context.<domain>.id` to the first element’s ID unless that would clobber an explicitly set current item.
- **Cross-links**
  - If a payload includes `projectId` along with `compileId`/`backtestId`/`optimizationId`, set all relevant namespaces in one pass.

## 4) Default Argument Resolution

When invoking a method, fill missing parameters in this order:

1. Explicit user input in the current turn.
2. Pinned context (e.g., `context.project.id`, `context.compile.id`).
3. By-name resolution: if the user gives a name (e.g., “project Alpha”), call `list_projects` and pick exact match; if multiple, ask user to disambiguate.
4. Most recent from `context.recent.<domain>` if semantically safe (e.g., reading a backtest right after creating one).
5. Fail fast with a precise message if no safe default exists.

### 4.1 Project-centric chaining
After `create_project`, set:

```
context.project = { id, name }
```

Reset: `context.compile`, `context.backtest`, `context.optimization` (they belong to the previous project).

- `create_compile` defaults `projectId ← context.project.id`.
- `create_backtest` defaults `projectId ← context.project.id`, `compileId ← context.compile.id`.

### 4.2 Backtest-centric chaining
After `create_backtest`, set `context.backtest.id`.

Readers/updates default to `context.backtest.id`:

- `read_backtest`, `read_backtest_chart`, `read_backtest_orders`, `read_backtest_insights`, `update_backtest`, `delete_backtest`.

### 4.3 Optimization-centric chaining
After `create_optimization`, set `context.optimization.id`.

Readers/updates default accordingly:

- `read_optimization`, `update_optimization`, `abort_optimization`, `delete_optimization`.

### 4.4 Live-centric chaining
After `create_live_algorithm`, set `context.live.id` and lock it to the active session unless explicitly changed or stopped.

Readers/controls default to `context.live.id`:

- `read_live_algorithm`, `read_live_chart`, `read_live_logs`, `read_live_portfolio`, `read_live_orders`, `read_live_insights`, `stop_live_algorithm`, `liquidate_live_algorithm`.

After `stop_live_algorithm` or `liquidate_live_algorithm`, unset `context.live.id`.

### 4.5 Files & object store
Track last touched file path and ID:

```
context.file.path, context.file.id
```

Track last object key / url job IDs:

```
context.object.key, context.object.jobId, context.object.downloadUrl
```

## 5) Sensible Defaults & Resets

- **New Project**
  - Set `context.project` and clear compile/backtest/optimization contexts.
- **Delete Project**
  - Clear all contexts tied to that project.
- **New Compile**
  - Overwrite `context.compile.id`.
- **New Backtest**
  - Overwrite `context.backtest.id`.
- **New Optimization**
  - Overwrite `context.optimization.id`.
- **New Live Deployment**
  - Overwrite `context.live.id`; keep prior deployments under `context.recent.live`.
- **Delete/Abort/Stop**
  - Clear only the relevant slice (e.g., abort optimization clears `context.optimization.id`).

## 6) Typical Flows (No ID Prompts)

### 6.1 Project → Compile → Backtest
1. `create_project` (capture `projectId`, name)
2. `create_file` / `update_file_contents` (optional)
3. `create_compile` (defaults to `context.project.id`; capture `compileId`)
4. `create_backtest` (defaults to `context.project.id` + `context.compile.id`; capture `backtestId`)
5. `read_backtest` / `read_backtest_chart` / `read_backtest_orders` / `read_backtest_insights`

### 6.2 Optimization
1. `create_optimization` (capture `optimizationId`)
2. `read_optimization` / `update_optimization` / `abort_optimization`

### 6.3 Live
1. `authorize_connection` (handle auth; no ID captured)
2. `create_live_algorithm` (capture `algorithmId`/`deployId` → `context.live.id`)
3. `read_live_*`, `stop_live_algorithm`, `liquidate_live_algorithm`

## 7) By-Name Resolution Heuristics

- **Projects**: If user says “open project Foo”, run `list_projects`, select an exact (case-insensitive) name match; if multiple, ask which one.
- **Backtests/Optimizations**: If user references a label or timestamp, prefer the most recent match for the current `projectId`.
- **Files**: If path is given, prefer path over name; otherwise, pick the last file touched in `context.file`.

## 8) AI Helpers & Safety Nets

Use helpers opportunistically without extra user input:

- `check_syntax` before compile if user edited code.
- `check_initialization_errors` before a backtest on a new project.
- `enhance_error_message` to summarize stack traces.
- `complete_code` and `update_code_to_pep8` on request or when user asks for fixes.

Store last helper outputs in:

```
context.ai.last = { tool, summary, timestamp }
```

## 9) Lean Versions & Server Metadata

On session start, call:

- `read_mcp_server_version` → store in `context.server.version`
- `read_lean_versions` → store in `context.lean.versions`

Use versions only for display and tooling hints; never to block a user unless an operation explicitly requires it.

## 10) Error Handling & Polling

- Long-running ops (`create_compile`, `create_backtest`, `create_optimization`, live reads):
  - Poll with backoff; surface status succinctly.
  - Keep the last known status in `context.status.<domain>`.
- Missing context: If a required ID can’t be resolved, respond with a single crisp question to disambiguate (e.g., “Which project? Alpha or Alpha-Research?”).

## 11) Future-Proofing

- **Unknown methods**: Treat any new tool `foo_bar_baz` as callable:
  - Pass through user-provided args.
  - Harvest any `*Id` keys from the response using the rules in §3.
- **Context schema growth**: It’s safe to extend `context.<domain>` with new IDs/handles without breaking existing defaults.

## 12) Minimal Examples

### Example A — Zero-ID project flow
**User**: “Create a new project ‘SignalLab’ and backtest it.”

**Client**:

```
create_project { name: "SignalLab" }
create_compile {}
create_backtest {}
```

(All IDs sourced from context; then auto-read the backtest.)

### Example B — Read last live portfolio
**User**: “What’s my live portfolio look like?”

**Client**:

- If `context.live.id` set → `read_live_portfolio {}`
- Else, `list_live_algorithms {}` → pick most recent active, set `context.live.id`, then `read_live_portfolio {}`

## 13) Context Snapshot (schema sketch)

```json
{
  "server": { "version": "…" },
  "lean": { "versions": ["…"] },
  "project": { "id": "...", "name": "..." },
  "compile": { "id": "..." },
  "backtest": { "id": "..." },
  "optimization": { "id": "..." },
  "live": { "id": "...", "command": { "id": "..." } },
  "file": { "id": "...", "path": "..." },
  "object": { "key": "...", "jobId": "...", "downloadUrl": "..." },
  "recent": {
    "projects": [],
    "backtests": [],
    "optimizations": [],
    "live": [],
    "files": [],
    "objects": []
  },
  "ids": { "deployId": "...", "algorithmId": "..." },
  "status": { "compile": "...", "backtest": "...", "optimization": "..." },
  "ai": { "last": { "tool": "check_syntax", "summary": "...", "timestamp": "..." } }
}
```

### One-liner for clients that showed only 4 tools at startup
If your client enumerates tools lazily, seed it with this registry (Section §2) and apply the universal rules (§3–§5). From that point, never prompt for `projectId`, `compileId`, `backtestId`, `optimizationId`, or live deployment IDs when context suffices.

