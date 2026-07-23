# NimCode

NimCode is an autonomous AI coding assistant powered by NVIDIA NIM APIs (LLaMa 3.1 70B, etc.). It works similarly to Claude Code, providing a standalone REPL, a powerful command-line interface, and smart code modification capabilities.

## Installation

You can install NimCode globally on your system using pip:

```bash
pip install .
```

After installation, the `nimcode` command will be available anywhere in your terminal.

## Setup

First, you need to configure your NVIDIA NIM API key:

```bash
nimcode login
```

Alternatively, set the `NIM_API_KEY` environment variable.

## Usage

You can start the interactive REPL by simply running:

```bash
nimcode
```

Or you can pass a direct task for one-off executions:

```bash
nimcode "Create a react application in the current directory"
nimcode /plan "Build a snake game in Python"
```

## Features

- **Plan Mode**: Run `/plan` to enter planning mode. The agent will read your codebase and generate a comprehensive markdown plan in `.nimcode/plans/`.
- **Skills/Memories**: NimCode learns over time and saves learned skills into `.nimcode/skills/` for future context.
- **Multimodal Vision**: Use `/vision` to analyze screenshots.
- **Voice Input**: Use `/voice` to speak to NimCode.
- **Auto-Commits**: Use `/commit` to auto-generate git commits.
- **Diagnostic Tool**: Run `nimcode doctor` to check your environment setup.
