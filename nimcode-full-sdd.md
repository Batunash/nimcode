# Software Design Document: NIM-Code
## A Full, Standalone Claude-Code-Equivalent CLI Agent for NVIDIA NIM API

**Version:** 3.0 (Full Scope)
**Status:** Draft
**Author:** Batuhan

---

## 1. Overview

`nimcode` is a terminal-native, agentic coding assistant that replicates the full Claude Code experience — not just "an LLM that can call tools," but the complete product surface: persistent project memory, a real permission system, session management, subagents, slash commands, hooks, plan mode, and context compaction — built from scratch in Python and driven entirely by NVIDIA NIM API models instead of Anthropic's API.

It is a standalone tool. It does not proxy Claude Code's protocol and does not depend on any third-party agent framework (no LangChain, no Aider, no OpenHands). The only external dependency for model access is a thin HTTP client against NIM's OpenAI-compatible `/v1/chat/completions` endpoint.

The central design problem this SDD solves: Claude Code assumes Anthropic-grade tool-calling reliability. NIM-hosted open models (Llama, Qwen, Mistral, DeepSeek, Nemotron, etc.) do not uniformly provide that. Every subsystem below is designed so that unreliable tool-calling degrades gracefully instead of breaking the whole product.

---

## 2. Goals & Non-Goals

### Goals
- Full CLI parity of *behavior* with Claude Code: `nimcode` in a project directory launches an interactive REPL; conversational, multi-turn, autonomous task execution; reads/writes files; runs shell commands; iterates until done.
- Persistent project memory (`NIMCODE.md`, equivalent to `CLAUDE.md`) that's automatically loaded into every session's system prompt.
- Full built-in tool set matching Claude Code: file read/write/edit, search, bash execution, todo tracking, subagent dispatch.
- Slash commands (`/init`, `/compact`, `/clear`, `/agents`, `/permissions`, custom user-defined commands).
- Plan mode: a read-only exploration mode that produces a plan before any file is touched.
- Context compaction when approaching the model's context limit, instead of hard failure or silent truncation.
- Hooks: user-definable shell commands that fire on lifecycle events (before tool use, after tool use, session start, etc.) — same extensibility model as Claude Code.
- Subagents: named, independently-scoped agent configs that can be dispatched for isolated subtasks (e.g., a "reviewer" subagent, a "test-runner" subagent).
- Optional MCP client support, so it can connect to the same MCP servers you already use (n8n workflows, custom tools) rather than reinventing every integration.
- Robust against unreliable tool-calling from NIM models via an automatic native/fallback compatibility layer.

### Non-Goals
- Not a hosted multi-tenant SaaS — single-user, local, per-project tool (same deployment model as Claude Code itself).
- Not targeting IDE-embedded extensions (VS Code/JetBrains plugins) in v1 — CLI only. Can be layered on later.
- Not attempting byte-for-byte terminal UI parity — functional and workflow parity matters, exact pixel/animation fidelity doesn't.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI / REPL Frontend                        │
│   nimcode │ nimcode -p "task" │ slash commands │ plan mode toggle  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │      Session         │  (conversation state,
                     │      Manager         │   NIMCODE.md loading,
                     └──────────┬──────────┘   resume/history)
                                │
                     ┌──────────▼──────────┐
                     │     Agent Loop        │
                     └──────────┬──────────┘
                                │
      ┌─────────────┬───────────┼────────────┬──────────────┐
      │             │           │            │              │
┌─────▼─────┐ ┌─────▼─────┐ ┌───▼────────┐ ┌─▼──────────┐ ┌─▼──────────┐
│ NIM Client │ │ Tool-Call  │ │  Context   │ │ Permission │ │  Hooks      │
│ (raw HTTP, │ │ Compat.    │ │  Manager   │ │  Engine    │ │  Engine     │
│  streaming)│ │ Layer      │ │ (compaction│ │ (confirm/  │ │ (lifecycle  │
│            │ │            │ │  repo map) │ │  auto-yes) │ │  triggers)  │
└─────┬─────┘ └─────┬─────┘ └───┬────────┘ └─┬──────────┘ └─┬──────────┘
      │             │           │            │              │
      │      ┌──────▼──────┐    │            │              │
      │      │Tool Registry │    │            │              │
      │      │ built-in +   │    │            │              │
      │      │ MCP + sub-   │    │            │              │
      │      │ agents       │    │            │              │
      │      └──────┬──────┘    │            │              │
      │             │           │            │              │
┌─────▼─────────────▼───────────▼────────────▼──────────────▼─────┐
│                Project Workspace (cwd, git-aware, sandboxed)       │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Core Components

### 4.1 NIM Client

Minimal wrapper (`httpx`) around NIM's OpenAI-compatible endpoint. Handles auth, SSE streaming parse, retry with exponential backoff + jitter on 429/5xx, per-request timeout, and token counting (tiktoken-style approximate counter — exact tokenizer varies by model family, so this is an estimate used only for context-budget decisions).

```python
class NimClient:
    def __init__(self, api_key: str, base_url: str, model: str): ...
    def chat(self, messages: list[dict], tools: list[dict] | None, stream: bool = True): ...
    def count_tokens_approx(self, messages: list[dict]) -> int: ...
```

### 4.2 Model Capability Profile

Local cache (`~/.nimcode/capabilities.json`), populated by `nimcode probe <model>` or auto-probed on first use:

```json
{
  "qwen/qwen2.5-coder-32b-instruct": {
    "native_tool_calling": true,
    "reliable_json": true,
    "max_context": 32768,
    "reliable_streaming": true,
    "last_probed": "2026-07-20"
  },
  "meta/llama-3.1-70b-instruct": {
    "native_tool_calling": false,
    "reliable_json": false,
    "max_context": 128000,
    "reliable_streaming": true,
    "last_probed": "2026-07-20"
  }
}
```

Re-probe manually (`nimcode probe <model> --force`) if a model's behavior seems to have drifted, since NIM-hosted models get updated server-side outside your control.

### 4.3 Tool-Calling Compatibility Layer

The component that directly targets your current failure mode. Two paths, chosen per-model from the capability profile:

**Native path** — pass `tools=[...]` per OpenAI function-calling spec; parse `message.tool_calls` directly; validate each call's `arguments` against the tool's JSON schema before execution.

**Fallback path** (default for most NIM-hosted open models) — system prompt instructs the model to emit exactly one tool call per turn as a fenced block:

```
<tool_call>
{"tool": "Edit", "args": {"file_path": "auth.py", "old_string": "...", "new_string": "..."}}
</tool_call>
```

Parser pipeline:
1. Regex-extract the block (tolerant of surrounding prose, markdown fences, or the model forgetting the closing tag).
2. Lenient JSON repair (trailing commas, single quotes, unescaped newlines inside strings, smart-quote substitution).
3. Schema validation against the tool's declared args.
4. On failure at any stage: one re-prompt with the exact error message, then fall back to surfacing the raw model output to the user rather than looping forever.
5. If the model emits multiple tool_call blocks in one response, execute only the first; queue the rest as unread — most weak models produce garbage after the first call anyway, so this avoids compounding errors.

Native/fallback decision is per-model and cached, but also has a **per-turn circuit breaker**: if native mode fails validation twice in a session, that session drops to fallback mode for its remainder rather than repeatedly failing.

### 4.4 Tool Registry

Full built-in set, matching Claude Code's actual tools:

| Tool | Behavior |
|---|---|
| `Read` | Read file (optional offset/limit for large files) |
| `Write` | Create or fully overwrite a file |
| `Edit` | Exact `old_string` → `new_string` replacement; **rejects if `old_string` isn't unique in the file** — same contract as Claude Code, removes ambiguity for weaker models |
| `Glob` | Pattern-based file finding |
| `Grep` | Content search (ripgrep-backed if available, Python fallback otherwise) |
| `Bash` | Shell command execution in the project directory, with output truncation for very long output |
| `TodoWrite` | Maintains a visible, structured task list for the current session |
| `Task` | Dispatches a subagent (see 4.8) for an isolated subtask, returns only its final result to the parent context |
| `WebFetch` (optional) | Fetches and summarizes a URL's content — only if network egress is permitted by config |

Schemas are kept flat and minimal deliberately — nested JSON args are the largest source of malformed tool calls from smaller models.

### 4.5 Session Manager & Project Memory

- On startup, looks for `NIMCODE.md` in the project root (equivalent to `CLAUDE.md`) — project-specific instructions, coding conventions, architecture notes — and injects it into the system prompt automatically.
- `/init` slash command: scans the project (file tree, package manifests, README) and generates a starter `NIMCODE.md` via one model call.
- Session history persisted to `~/.nimcode/sessions/<project-hash>/<session-id>.jsonl` — supports `nimcode --resume` to continue the last session, and `nimcode --resume <id>` for a specific one.
- Global user preferences at `~/.nimcode/NIMCODE.md` (equivalent to Claude Code's user-level `CLAUDE.md`) — e.g., "always respond with Turkish UI labels but English code comments," reused across all your projects.

### 4.6 Context Manager & Compaction

- Tracks all files read/edited this session, kept in full in context; everything else summarized or excluded.
- Token budget from the model's capability profile (`max_context`), with a safety margin (e.g., trim at 80% of limit).
- **Compaction**: when nearing the limit, instead of hard-truncating, ask the model itself to produce a condensed summary of the conversation so far (one extra model call), replace the old messages with that summary, and continue — same mechanism as Claude Code's `/compact`. Available both as an automatic trigger and as a manual `/compact` slash command.
- Lightweight repo map (file tree + top-level function/class signatures, generated via a fast AST parse, not a model call) included in the system prompt so the model has structural awareness without needing every file in context.

### 4.7 Permission Engine

- Read-only tools (`Read`, `Glob`, `Grep`) auto-approved.
- Mutating tools (`Write`, `Edit`, `Bash`) show a diff/command preview and require interactive confirmation by default.
- Three modes, matching Claude Code:
  - **default** — confirm every mutating action.
  - **acceptEdits** — auto-approve file edits, still confirm `Bash`.
  - **bypassPermissions** (`--yolo` flag or `/permissions bypass`) — auto-approve everything; intended for scripted/non-interactive runs (e.g., triggered from your n8n pipeline).
- Per-project allow/deny lists in `.nimcode/settings.json` (e.g., always allow `pytest`, always deny `rm -rf`).

### 4.8 Subagents

- Defined in `.nimcode/agents/<name>.md`: a name, a system-prompt fragment, an allowed tool subset, and optionally a different NIM model (e.g., a cheaper/faster model for a "file-search" subagent, a stronger one for a "code-review" subagent).
- Dispatched via the `Task` tool: the parent agent hands off a bounded subtask, the subagent runs its own isolated agent loop with its own context window, and only its final result is returned to the parent — keeps the parent's context clean, exactly like Claude Code's subagent model.
- `/agents` slash command lists available subagents and lets you create/edit them interactively.

### 4.9 Hooks

- Config in `.nimcode/settings.json`, keyed by lifecycle event: `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`.
- Each hook is an arbitrary shell command; receives event context as JSON on stdin; can block the action (non-zero exit) with a message shown to the model.
- Example: a `PreToolUse` hook on `Bash` that blocks any command containing `rm -rf`, independent of the permission engine, for a hard safety net.
- Example: a `PostToolUse` hook on `Edit` that runs your linter/formatter automatically after every file edit.

### 4.10 Slash Commands

Built-in:
- `/init` — generate `NIMCODE.md` for the current project.
- `/compact` — manually trigger context compaction.
- `/clear` — start a fresh session, discarding history.
- `/agents` — manage subagents.
- `/permissions` — view/change the current permission mode.
- `/model` — switch the active NIM model mid-session.
- `/cost` — show estimated token usage for the session (NIM billing/rate-limit awareness).

Custom: any Markdown file in `.nimcode/commands/<name>.md` becomes `/<name>`, with its content used as a prompt template (supports `$ARGUMENTS` substitution) — same extensibility model as Claude Code's custom slash commands.

### 4.11 Plan Mode

- Toggled via `/plan` or a CLI flag.
- In plan mode, only read-only tools (`Read`, `Glob`, `Grep`, `Task` with read-only subagents) are permitted — `Write`/`Edit`/`Bash` calls are intercepted and rejected with a message telling the model to describe the plan instead of executing it.
- Agent produces a structured plan (steps, files to be touched, risks); user reviews and explicitly exits plan mode to let execution proceed.

### 4.12 MCP Client Support (optional, Phase 5)

- `nimcode` can act as an MCP client, connecting to MCP servers declared in `.nimcode/settings.json` (`mcpServers` block, same shape as Claude Code's config) — this lets it reuse any MCP servers you already run for n8n/other tools rather than reimplementing those integrations.
- MCP tool results go through the same Tool-Calling Compatibility Layer as built-in tools, since a weak NIM model won't distinguish between "built-in tool" and "MCP tool" in how reliably it calls them.

---

## 5. Agent Loop (detailed)

```
1. Session Manager loads NIMCODE.md (project + global), repo map, session history
2. Build message list: system prompt (identity + tool instructions + project memory) + history + latest user turn
3. Context Manager checks token budget → triggers compaction if needed
4. NIM Client sends request (native tools param or fallback prompt instructions, per capability profile)
5. Response arrives:
   a. Plain text → show to user, end turn
   b. Tool call → Tool-Calling Compatibility Layer parses/validates
      → Permission Engine checks if confirmation is required
      → Hooks Engine runs PreToolUse hooks (can block)
      → Tool Registry executes (built-in, subagent via Task, or MCP)
      → Hooks Engine runs PostToolUse hooks
      → Result appended as next message → back to step 3
6. Stuck-detection: if the last N tool calls are near-duplicate (same file/command/error) → halt, surface to user instead of looping
```

---

## 6. Configuration

`.nimcode/settings.json` (project-level):

```json
{
  "model": "qwen/qwen2.5-coder-32b-instruct",
  "baseUrl": "https://integrate.api.nvidia.com/v1",
  "apiKeyEnv": "NIM_API_KEY",
  "toolCalling": "auto",
  "permissionMode": "default",
  "allowedCommands": ["pytest", "npm test", "dotnet test"],
  "deniedCommands": ["rm -rf"],
  "maxTurns": 30,
  "stuckDetectionWindow": 3,
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash", "command": "./scripts/check-command.sh" }],
    "PostToolUse": [{ "matcher": "Edit", "command": "./scripts/format.sh" }]
  },
  "mcpServers": {}
}
```

`~/.nimcode/settings.json` — same shape, user-level defaults applied across all projects.

---

## 7. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| HTTP/streaming | `httpx` | native SSE support, async + sync |
| CLI/REPL | `typer` (commands) + `prompt_toolkit` (interactive input, multi-line, history) | |
| Terminal rendering | `rich` | diffs, tables, spinners, markdown rendering |
| JSON repair | small hand-written lenient parser, extended as you encounter model-specific quirks | |
| AST/repo map | `ast` (stdlib) for Python projects; extend per-language as needed | |
| Diffing | `difflib` (stdlib) | sufficient for Edit previews |
| Persistence | plain JSON/JSONL files under `~/.nimcode/` — no database required for a single-user CLI | |
| Search | `ripgrep` binary if present on PATH, Python `re`-based fallback otherwise | |

No agent framework (no LangChain, no Aider, no OpenHands) — the agent loop, tool schema, and parsing are all custom code you own end-to-end, which matters because debugging NIM-specific tool-calling quirks requires full visibility into every request/response.

---

## 8. Implementation Phases

**Phase 1 — Core loop + native tool calling**
NIM Client, basic agent loop, `Read`/`Write`/`Bash` only, native `tools` param against one model known to support it well. Prove the end-to-end loop works.

**Phase 2 — Tool-calling compatibility layer**
Capability probing, fallback `<tool_call>` protocol, lenient JSON parser, re-prompt-on-parse-failure, per-turn circuit breaker. This is the fix for your current failures — prioritize this before anything else below.

**Phase 3 — Full built-in tool set**
`Edit` (with uniqueness contract), `Glob`, `Grep`, `TodoWrite`. Permission Engine with the three modes.

**Phase 4 — Session & memory**
`NIMCODE.md` loading, `/init`, session persistence + resume, repo map, context compaction (`/compact` + automatic trigger).

**Phase 5 — Extensibility**
Subagents (`Task` tool, `.nimcode/agents/`), Hooks Engine, custom slash commands, plan mode.

**Phase 6 (optional) — MCP client**
Connect to existing MCP servers (including anything you already run via n8n) so tool coverage extends without reimplementing integrations.

---

## 9. Testing Strategy

- Unit tests for the lenient JSON parser against a corpus of real malformed outputs (collect these from your current broken proxy setup — they're your best real-world fixtures).
- Integration test matrix across at least one native-tool-calling-capable model and one fallback-only model, running the same task set (fix a bug, add a feature, run and fix tests) to confirm both paths reach completion.
- Permission Engine tests: confirm mutating tools are correctly blocked/allowed per mode, and that hooks can override.
- Compaction correctness test: verify a compacted session retains enough information for the agent to correctly continue a multi-step task.
- Subagent isolation test: confirm a subagent's intermediate tool calls don't leak into the parent's context, only its final result does.

---

## 10. Known Risks

| Risk | Mitigation |
|---|---|
| NIM-hosted model output format drifts after a provider-side update | Capability profile has a `last_probed` timestamp; support manual re-probe |
| Fallback tool-calling costs more tokens/turn than native | Acceptable, paid only by models that actually need it (per profile) |
| Weak model produces a plausible-looking but wrong `Edit` | Uniqueness contract on `old_string` forces rejection instead of silent misapplication |
| Long autonomous loops burn through NIM free-tier rate limits | Exponential backoff + jitter in NIM Client; `maxTurns` cap; stuck-detection halts dead loops early |
| Hooks or Bash commands doing something destructive | Deny-list defaults (e.g., block `rm -rf` at the hook layer, independent of the LLM's judgment) |

---

## 11. Open Questions

- Multi-model routing within one session (cheap model for repo-map/summarization, strong model for actual edits) — worth adding in a later phase once the core is stable?
- Should session logs sync to Supabase (as in your other projects) for cross-device resume, or stay purely local for v1?
