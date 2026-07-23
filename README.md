<div align="center">
  
# 🚀 NimCode

**The Autonomous AI Coding Assistant for the NVIDIA NIM Ecosystem**

[![PyPI version](https://badge.fury.io/py/nimcode.svg)](https://badge.fury.io/py/nimcode)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*A powerful, standalone REPL and CLI agent that writes, edits, and plans code like a senior developer—powered by LLaMa 3.1 70B and the lightning-fast NVIDIA NIM API.*

</div>

---

## 🌟 Features

- 🧠 **Smart Planning (`/plan`)**: Generates comprehensive, step-by-step architectural plans directly into `.nimcode/plans/`.
- 🛠️ **Autonomous Execution (`/code`)**: Reads, writes, and tests code across your entire workspace.
- 📸 **Vision Support (`/vision`)**: Analyze screenshots to debug UI issues or write code from design mockups.
- 🎙️ **Voice Commands (`/voice`)**: Speak your requirements and let the agent do the typing.
- 💾 **Continuous Learning**: Saves custom rules and instructions to `.nimcode/skills/` so it gets smarter over time.
- 🤖 **Auto-Commits (`/commit`)**: Automatically writes descriptive, conventional git commits for your changes.

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

## ⚙️ How it Works

NimCode creates a `.nimcode` directory inside your projects. This directory acts as the "brain" for that specific workspace:
- `.nimcode/plans/`: All your generated step-by-step markdown plans live here.
- `.nimcode/skills/`: Any custom guidelines, framework rules, or memories you teach the agent.

## 🛡️ Requirements

- Python 3.8+
- An NVIDIA NIM API Key (NIM_API_KEY)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check out our [issues page](#).

---
<div align="center">
<i>Built with ❤️ for the open-source developer community.</i>
</div>
