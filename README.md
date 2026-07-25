<div align="center">
  
# 🚀 NimCode

**The Autonomous AI Coding Assistant for the NVIDIA NIM Ecosystem**

[![PyPI version](https://badge.fury.io/py/nimcode.svg)](https://badge.fury.io/py/nimcode)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*A powerful, standalone REPL and CLI agent that writes, edits, and plans code like a senior developer—powered by LLaMa 3.1 70B (and other cutting-edge models) and the lightning-fast NVIDIA NIM API.*

</div>

---

## 🌟 Overview

NimCode is your autonomous coding pair-programmer. Built with a rich interactive terminal interface, it doesn't just autocomplete code—it plans architectures, executes terminal commands, writes complete files, formats code automatically, and manages your workspace. 

### 🛠️ What We've Built So Far
- **VS Code Deep Integration**: Native IPC communication allowing NimCode to read active editors, send patches, and act as your intelligent coding panel within VS Code.
- **RAG & Semantic Search**: Zero-dependency TF-IDF/BM25 based indexer that instantly scans massive workspaces and retrieves context-aware code snippets.
- **Autonomous Auto-Fixer**: The `/fix` command creates a self-healing feedback loop—it runs your broken commands, analyzes the tracebacks, and automatically iterates on code patches until the build passes.
- **Multi-Model & Local Support**: Flexible `api_base_url` configuration to seamlessly switch between NVIDIA NIM, Ollama, or vLLM endpoints.
- **Smart Permission Engine**: Granular control over file writes and command executions, featuring an auto-bypass mechanism and interactive `(a)ccept / (r)eject` diff previews.
- **Robust Interactive REPL**: Multiline support (Alt+Enter), syntax highlighting, and beautiful `rich`-powered UI menus.
- **Automated Workflows**: Automatic linting and formatting using `black`, `flake8`, and `prettier` behind the scenes.
- **Model Context Protocol (MCP)**: Native integration for MCP tools allowing infinite extensibility.

### 🚀 What We're Working On (Roadmap)
- **Sub-agent Swarms**: Perfecting `/delegate` and `/swarm` to distribute complex tasks among specialized AI roles.
- **Advanced Diagnostics**: Refining `/bughunter`, `/security-review`, and `/doctor` for automated codebase auditing.
- **Test-Driven Development**: Upgrading `/tdd` and `/testgen` to automatically write tests and ensure 100% coverage before committing.
- **Infrastructure & DevOps**: Implementing `/terraform-god` and `/sql-tune` for automated cloud provisioning and database query optimization.

---

## 📦 Installation

NimCode is available globally via PyPI. You can install it anywhere in seconds:

```bash
pip install nimcode
```

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

Inside the `nimcode` REPL, you can type natural language or use any of the following slash commands to trigger specific workflows:

### Mode Toggles & Execution
- **`/code`**: Enter standard coding mode (default mode, prompts for dangerous actions).
- **`/plan`**: Enter planning mode (read-only safe mode). The AI will research and write a markdown plan before modifying code.
- **`/trust`**: Enter trust mode. The AI will run commands and edit files completely autonomously without asking for `(a)ccept / (r)eject`.
- **`/untrust`**: Disable trust mode and restore permission prompts.

### Interface & Settings
- **`/models`**: Open an interactive UI to select your preferred NVIDIA NIM model (e.g., meta/llama-3.1-70b-instruct).
- **`/theme`**: Open an interactive UI to change your syntax highlighting theme (e.g., monokai, dracula, nord, github).
- **`/config`**: View and edit global NimCode configuration settings.

### Workspace & Context Management
- **`/clear`**: Clear the current conversation history to reset context.
- **`/compact`**: Compact the context window to save tokens while keeping essential memories.
- **`/context`**: View and manage the loaded context window.
- **`/rewind`**: Rewind the conversation history by a few steps.
- **`/undo`**: Revert the last file modification made by the AI.

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
- **`/sql-tune`**: Database telepathy mode. Analyzes and auto-tunes SQL queries for maximum performance.
- **`/terraform-god`**: Cloud architect mode. Auto-provisions scalable best-practice Terraform infrastructure.
- **`/decompile <binary>`**: Reverse engineering mode using tools like `objdump` and `radare2`.

### AI & Agents
- **`/delegate <role> <task>`**: Spawn an independent sub-agent with a specific role to handle a background task.
- **`/swarm`**: Orchestrate multiple sub-agents to tackle a complex architectural epic simultaneously.
- **`/grill-me`**: Interrogation mode. The AI will ask *you* hard questions to refine your system design and edge cases.
- **`/learn`**: Teach NimCode a new persistent skill or framework rule that it will remember for future sessions.
- **`/vision`**: Capture the screen and analyze UI elements using Vision AI models.
- **`/voice`**: Record your voice for 5 seconds and transcribe it as a prompt.
- **`/mcp install`**: Install and configure new Model Context Protocol tools.

---

## ⚙️ How it Works

NimCode creates a `.nimcode` directory inside your projects. This directory acts as the "brain" for that specific workspace:
- `.nimcode/plans/`: All your generated step-by-step markdown plans live here.
- `.nimcode/skills/`: Any custom guidelines, framework rules, or memories you teach the agent.
- `.nimcode/history/`: File backups for `/undo` capabilities.

### Advanced Configuration

NimCode's behavior can be fully customized through `~/.nimcode/settings.json` (global) or `.nimcode/settings.json` (per-project). Setting any timeout to `0` disables it (infinite).

```json
{
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

## 🛡️ Requirements

- Python 3.8+
- An NVIDIA NIM API Key (`NIM_API_KEY`)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check out our [issues page](#).

---
<div align="center">
<i>Built with ❤️ for the open-source developer community.</i>
</div>
