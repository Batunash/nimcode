<div align="center">
  
# 🚀 NimCode

**The Autonomous AI Coding Assistant for the NVIDIA NIM Ecosystem**

[![PyPI version](https://img.shields.io/pypi/v/nimcode.svg)](https://pypi.org/project/nimcode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*A powerful, standalone REPL and CLI agent that writes, edits, and plans code like a senior developer—powered by LLaMa 3.1 70B (and other cutting-edge models) and the lightning-fast NVIDIA NIM API.*

</div>

---

## 🌟 Overview

NimCode is your autonomous coding pair-programmer. Built with a rich interactive terminal interface, it doesn't just autocomplete code—it plans architectures based on real documents (SDD, PRD, RFC), executes terminal commands, writes complete files, and manages your workspace.

### ✅ What Works Right Now
- **OS-Aware Agent**: Automatically detects Windows/Linux/macOS and uses the correct shell commands. No more `mkdir -p` on Windows.
- **SDD/PRD-Aware Planning**: `/plan` mode reads your actual documents and produces implementation plans grounded in real file names, modules, and requirements—not generic PM templates.
- **Paginated File Reading**: Large files (like SDDs) are read in chunks with `offset`/`limit` so nothing gets truncated.
- **VS Code Deep Integration**: Native IPC communication allowing NimCode to read active editors, send patches, and act as your intelligent coding panel within VS Code.
- **RAG & Semantic Search**: Zero-dependency TF-IDF/BM25 based indexer that instantly scans massive workspaces and retrieves context-aware code snippets.
- **Autonomous Auto-Fixer**: The `/fix` command creates a self-healing feedback loop—runs your broken commands, analyzes tracebacks, and automatically iterates on code patches until the build passes.
- **Multi-Model & Local Support**: Flexible `api_base_url` configuration to seamlessly switch between NVIDIA NIM, Ollama, or vLLM endpoints. Dynamic model list fetched from the API at runtime.
- **Smart Permission Engine**: Granular control over file writes and command executions, featuring an auto-bypass mechanism and interactive `(a)ccept / (r)eject` diff previews. Non-interactive/CI mode is secure by default (Bash denied unless explicitly allowed).
- **Robust Interactive REPL**: Multiline support (Alt+Enter), syntax highlighting, and beautiful `rich`-powered UI menus.
- **Automated Workflows**: Automatic linting and formatting using `black`, `flake8`, and `prettier` behind the scenes.
- **Model Context Protocol (MCP)**: Native integration for MCP tools allowing infinite extensibility.
- **Context Management**: Auto-compact with per-model context window awareness. `/thinkback` shows real session statistics.
- **Live Sync**: Workspace watcher automatically updates the repo map in the agent's context when files change.

### 🚀 What We're Working On (Roadmap)
- **Sub-agent Swarms**: Perfecting `/delegate` and `/swarm` to distribute complex tasks among specialized AI roles.
- **Advanced Diagnostics**: Refining `/bughunter`, `/security-review`, and `/doctor` for automated codebase auditing.
- **Test-Driven Development**: Upgrading `/tdd` and `/testgen` to automatically write tests and ensure 100% coverage before committing.
- **Infrastructure & DevOps**: Implementing `/terraform-god` and `/sql-tune` for automated cloud provisioning and database query optimization.

---

## 📦 Installation & Update

```bash
# First time install
pip install nimcode

# Update to latest version
pip install --upgrade nimcode
```

> **⚠️ If NimCode shows an old version number at startup**, you likely have an older install. Run `pip install --upgrade nimcode` to get the latest fixes.

## 🚀 Quick Start

1. **Get an API Key**: Grab a free NVIDIA API key from [build.nvidia.com](https://build.nvidia.com/).
2. **Login**: Connect your local environment by running:
   ```bash
   nimcode login
   ```
3. **Start Coding**: 
   - Launch the interactive REPL:
     ```bash
     nimcode
     ```
   - Or run a one-off task directly from the command line:
     ```bash
     nimcode /plan "Build a classic Snake game using HTML5 Canvas"
     ```

---

## 💻 Complete Command Reference

Inside the `nimcode` REPL, you can type natural language or use any of the following slash commands:

### Mode Toggles & Execution
- **`/code`**: Enter standard coding mode (default mode, prompts for dangerous actions).
- **`/plan`**: Enter planning mode. NimCode will **read your actual documents/files first**, then write a concrete implementation plan to `.nimcode/plans/`.
- **`/trust`**: Enter trust mode. The AI will run commands and edit files completely autonomously without asking for `(a)ccept / (r)eject`. Turn limit removed.
- **`/untrust`**: Disable trust mode and restore permission prompts.

### Interface & Settings
- **`/models`**: Open an interactive UI to select your preferred NVIDIA NIM model.
- **`/theme`**: Open an interactive UI to change your syntax highlighting theme.
- **`/config`**: View and edit global NimCode configuration settings.

### Workspace & Context Management
- **`/clear`**: Clear the current conversation history to reset context.
- **`/compact`**: Compact the context window to save tokens while keeping essential memories.
- **`/context`**: View and manage the loaded context window.
- **`/rewind`**: Rewind the conversation history by a few steps.
- **`/undo`**: Revert the last file modification made by the AI.
- **`/thinkback`**: View real session statistics (turns, token estimates, message history).

### Project & Search
- **`/index`**: Index the current project files to enable lightning-fast Semantic Search.
- **`/map`**: Generate a high-level semantic architecture map of the codebase.
- **`/research`**: Enter deep-research mode for reading documentation or large files.

### Automation & Git
- **`/commit`**: Analyze all staged git changes and automatically generate a conventional commit message.
- **`/fix`**: Run a specific shell command and let the AI automatically iterate to fix any resulting errors.
- **`/autofix-pr`**: Pulls the current active GitHub Pull Request, reads comments, and automatically fixes the mentioned issues.

### Advanced Development Modes
- **`/testgen <file>`**: Generate unit tests for a specific file, aiming for 100% coverage.
- **`/tdd`**: Enter Test-Driven Development mode. The AI will write tests first, verify they fail, and then implement the code to pass them.
- **`/bughunter`**: Initiate an automated search for logical bugs and edge cases across the codebase.
- **`/security-review`**: Audit the codebase for common vulnerabilities (e.g., OWASP top 10).
- **`/ultraplan <task>`**: Generate a master ultra-detailed, dependency-graphed execution plan.

### AI & Agents
- **`/delegate <role> <task>`**: Spawn an independent sub-agent with a specific role to handle a background task.
- **`/swarm`**: Orchestrate multiple sub-agents to tackle a complex architectural epic simultaneously.
- **`/grill-me`**: Interrogation mode. The AI will ask *you* hard questions to refine your system design and edge cases.
- **`/learn`**: Teach NimCode a new persistent skill or framework rule that it will remember for future sessions.
- **`/vision`**: Capture the screen and analyze UI elements using Vision AI models.
- **`/mcp install`**: Install and configure new Model Context Protocol tools.

---

## ⚙️ How it Works

NimCode creates a `.nimcode` directory inside your projects. This directory acts as the **agent's personal workspace**, not your project's source code:
- `.nimcode/plans/`: All generated step-by-step markdown plans live here.
- `.nimcode/skills/`: Custom guidelines, framework rules, or memories you teach the agent.
- `.nimcode/history/`: File backups for `/undo` capabilities.

> **Important**: NimCode writes your actual source code to your project root, not inside `.nimcode/`. The `.nimcode/` folder is only for the agent's internal notes.

### Advanced Configuration

NimCode's behavior can be fully customized through `~/.nimcode/settings.json` (global) or `.nimcode/settings.json` (per-project). Setting any timeout to `0` disables it (infinite).

```json
{
    "model": "meta/llama-3.1-70b-instruct",
    "api_base_url": "https://integrate.api.nvidia.com/v1",
    "timeout_command": 1200,
    "timeout_llm": 120,
    "timeout_format": 10,
    "timeout_browser": 15000,
    "timeout_updater": 3,
    "max_turns": 200,
    "max_tokens": 120000,
    "max_retries": 15,
    "retry_base_delay": 2.0,
    "retry_max_delay": 60.0,
    "allow_bash_non_interactive": false
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | `meta/llama-3.1-70b-instruct` | Default LLM model |
| `api_base_url` | NVIDIA NIM endpoint | Switch to Ollama/vLLM by changing this |
| `timeout_command` | 1200 | Max seconds for bash commands (0 = infinite) |
| `timeout_llm` | 120 | Max seconds for LLM API calls (0 = infinite) |
| `timeout_format` | 10 | Max seconds for formatters like black/prettier |
| `timeout_browser` | 15000 | Max ms for browser actions |
| `timeout_updater` | 3 | Max seconds for update checks |
| `max_turns` | 200 | Max agent turns per session (0 = unlimited) |
| `max_tokens` | 120000 | Token budget before auto-compact |
| `max_retries` | 15 | Max API retry attempts on transient errors |
| `retry_base_delay` | 2.0 | Base delay for exponential backoff (seconds) |
| `retry_max_delay` | 60.0 | Max delay cap for backoff (seconds) |
| `allow_bash_non_interactive` | false | Allow Bash commands in non-interactive/CI mode |

---

## 📋 Changelog

### v0.5.2 (Latest)
- 🧠 **Autonomous Marathon Runner**: Capable of running non-stop for 5-6 hours without drifting from the main plan.
- 🧪 **Native TestRunner**: NimCode can now run your test suites (`pytest`, `npm test`, `go test`) and self-heal its code until the tests pass.
- 🗺️ **Semantic AST Explorer**: `GetCodeOutline` tool added for instant navigation within large files (functions/classes with line numbers) instead of reading thousands of lines.
- 🛡️ **Stuck-Loop Breaker**: AI no longer gets stuck repeating the same failing action. Auto-detects 3x repeated errors and forces a strategy change.
- 🧭 **Plan-Drift Radar**: Automatically pings the agent every 15 turns to ensure strict compliance with the `.nimcode/active_plan.txt` and prevents hallucinations.
- 🚨 **Anti-Laziness Firewall**: Advanced regex intercepts lazy code (e.g., `// TODO`, `pass`) before it's written and forces the AI to output complete logic.
- ✨ **Self-Correcting Auto-Linters**: Seamless multi-language support. Formats and validates code in the background using `go vet`, `prettier`, and `python` syntax checks.
- 🧠 **Semantic Context RAG**: Automatically pins the directory tree and database schemas into the system prompt to cure agent amnesia.
- 📝 **ReplaceBlock Tool**: Precision line-based editing replaces the buggy exact-string `Replace` tool, completely solving indentation mismatch errors.
- ✅ **195 tests passing**

### v0.4.0
- 🐛 **System prompt is now OS-aware**: Correctly uses Windows (`mkdir`, `copy`) or Unix (`mkdir -p`, `cp`) commands based on the detected OS
- 🐛 **Plan quality massively improved**: `/plan` mode now reads your actual documents (SDD, PRD, etc.) and generates concrete plans with real file paths and code — not generic PM templates
- 🐛 **Fixed `_distill_memory` 400 error**: Context compaction no longer crashes with a Bad Request error
- 🐛 **Fixed version tracking**: `CURRENT_VERSION` was hardcoded as `3.0.0`; now reads from a single source of truth
- 🐛 **`/thinkback` shows real data**: Previously showed hardcoded fake table; now shows actual session statistics
- 🐛 **LiveSync fixed**: `repo_map` module was missing, causing the workspace watcher to silently fail
- 🔒 **Security**: Non-interactive mode no longer auto-approves Bash commands
- ⚙️ **Fully configurable**: `max_turns`, `max_tokens`, `max_retries`, retry delays all configurable via settings
- ⚙️ **Dynamic model list**: Fetched from NIM API at runtime with fallback to known models
- ⚙️ **Paginated file reading**: `Read` tool supports `offset`/`limit` for large files

### v0.3.4
- All timeouts configurable via settings (0 = infinite)

---

## 🛡️ Requirements

- Python 3.8+
- An NVIDIA NIM API Key (`NIM_API_KEY`)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check out our [issues page](#).

---
<div align="center">
<i>Built with ❤️ for the open-source developer community.</i>
</div>
