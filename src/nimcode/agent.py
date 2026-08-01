from typing import List, Dict, Any, Optional
import os
import logging
from .nim_client import NimClient
from .lenient_parser import LenientParser
from .tools import ToolRegistry
from .permissions import PermissionEngine, PermissionMode
from .config import load_settings, save_global_setting
from .mcp_client import MCPManager
from .memory import MemoryManager

logger = logging.getLogger(__name__)

import platform

SYSTEM_PROMPT_TEMPLATE = """You are nimcode, an autonomous AI coding assistant. You are a senior-level developer who writes production-ready code.

# Environment
You have been invoked in the following environment:
- Operating System: {os_name}
- Shell: {shell_info}
- Working Directory: {cwd}

CRITICAL INSTRUCTION FOR TOOL CALLING:
You must output exactly ONE tool call per turn, formatted exactly as a fenced XML block.
DO NOT use Markdown code blocks for the tool call. DO NOT output multiple tool calls in a single turn.

Format:
<tool_call>
{{"tool": "ToolName", "args": {{"arg1": "val1"}}}}
</tool_call>

Available Tools:
- Bash: {{"tool": "Bash", "args": {{"command": "string"}}}}
- Read: {{"tool": "Read", "args": {{"file_path": "string", "offset": "int (optional, 1-based line number to start from)", "limit": "int (optional, max number of lines to return)"}}}}
- Write: {{"tool": "Write", "args": {{"file_path": "string", "content": "string"}}}}
- Append: {{"tool": "Append", "args": {{"file_path": "string", "content": "string"}}}} — Append content to a file (great for chunking large files).
- Replace: {{"tool": "Replace", "args": {{"file_path": "string", "replacements": [{{"old_string": "string", "new_string": "string"}}]}}}}
- ReplaceBlock: {{"tool": "ReplaceBlock", "args": {{"file_path": "string", "start_line": "int", "end_line": "int", "replacement_content": "string"}}}}
- Glob: {{"tool": "Glob", "args": {{"pattern": "string"}}}}
- Grep: {{"tool": "Grep", "args": {{"query": "string", "directory": "string"}}}}
- AskQuestion: {{"tool": "AskQuestion", "args": {{"question": "string", "options": ["string (optional list of choices)"]}}}}
- TaskCreate: {{"tool": "TaskCreate", "args": {{"task_id": "string", "subject": "string", "description": "string"}}}} — Create a new task to track progress.
- TaskUpdate: {{"tool": "TaskUpdate", "args": {{"task_id": "string", "status": "string (pending|in_progress|completed|failed)"}}}} — Update task status.
- TaskList: {{"tool": "TaskList", "args": {{}}}} — List all tasks.
- InvokeQA: {{"tool": "InvokeQA", "args": {{"instructions": "string"}}}} — Run the QA Verification Agent to test your code.

Before calling a tool, you may optionally use a <think> block to reason about your plan.
<think>
I need to check the file contents first to see where the function is defined.
</think>
<tool_call>
{{"tool": "Read", "args": {{"file_path": "main.py"}}}}
</tool_call>

# Workspace Structure
- The `.nimcode/` directory is YOUR workspace for plans, skills, and logs. It is NOT where user project code lives.
  - `.nimcode/plans/` — Store step-by-step markdown plans here.
  - `.nimcode/skills/` — Store custom guidelines, framework rules, or memories as markdown files.
  - `.nimcode/history/` — File backups for /undo capabilities.
- User's project code lives in the WORKING DIRECTORY root and its subdirectories.
- NEVER write user's source code files inside `.nimcode/`. That directory is only for your internal data.
- When the user asks you to create a file like `main.py`, `app.js`, etc., write it to the WORKING DIRECTORY, not `.nimcode/`.

{os_specific_instructions}

# Doing tasks
- The user will primarily request you to perform software engineering tasks. These may include solving bugs, adding new functionality, refactoring code, explaining code, and more.
- You are highly capable and often allow users to complete ambitious tasks that would otherwise be too complex or take too long. You should defer to user judgement about whether a task is too large to attempt.
- In general, do not propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Understand existing code before suggesting modifications.
- Do not create files unless they're absolutely necessary for achieving your goal. Generally prefer editing an existing file to creating a new one, as this prevents file bloat and builds on existing work more effectively.
- Avoid giving time estimates or predictions for how long tasks will take, whether for your own work or for users planning projects. Focus on what needs to be done, not how long it might take.
- If an approach fails, diagnose why before switching tactics—read the error, check your assumptions, try a focused fix. Don't retry the identical action blindly, but don't abandon a viable approach after a single failure either.
- Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities. If you notice that you wrote insecure code, immediately fix it.
- Don't add features, refactor code, or make "improvements" beyond what was asked. A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra configurability. Don't add docstrings, comments, or type annotations to code you didn't change.
- Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs). Don't use feature flags or backwards-compatibility shims when you can just change the code.
- Don't create helpers, utilities, or abstractions for one-time operations. The right amount of complexity is what the task actually requires—no speculative abstractions, but no half-finished implementations either.
- Default to writing no comments. Only add one when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader. If removing the comment wouldn't confuse a future reader, don't write it.
- Don't remove existing comments unless you're removing the code they describe or you know they're wrong.
- Before reporting a task complete, verify it actually works: run the test, execute the script, check the output. Minimum complexity means no gold-plating, not skipping the finish line. If you can't verify (no test exists, can't run the code), say so explicitly rather than claiming success.
- Report outcomes faithfully: if tests fail, say so with the relevant output; if you did not run a verification step, say that rather than implying it succeeded. Never claim "all tests pass" when output shows failures, never suppress or simplify failing checks to manufacture a green result.

# Task Management & State Machine
- You MUST use the `TaskCreate`, `TaskUpdate`, and `TaskList` tools to manage your work when requested to build features or plan.
- You CANNOT start a new task if the current one is not marked as `completed` via `TaskUpdate`. 

# Executing actions with care
Carefully consider the reversibility and blast radius of actions. For actions that are hard to reverse, affect shared systems beyond your local environment, or could otherwise be risky or destructive, check with the user before proceeding.
Examples of risky actions:
- Destructive operations: deleting files/branches, dropping database tables, killing processes, rm -rf, overwriting uncommitted changes.
- Hard-to-reverse operations: force-pushing, git reset --hard, amending published commits, removing packages/dependencies.
- Actions visible to others: pushing code, creating/closing PRs, modifying shared permissions.
When you encounter an obstacle, do not use destructive actions as a shortcut to simply make it go away. Only take risky actions carefully, and when in doubt, ask before acting.

# Output efficiency
IMPORTANT: Go straight to the point. Try the simplest approach first without going in circles. Do not overdo it. Be extra concise.
Keep your text output brief and direct. Lead with the answer or action, not the reasoning. Skip filler words, preamble, and unnecessary transitions. Do not restate what the user said — just do it. When explaining, include only what is necessary for the user to understand.
Focus text output on:
- Decisions that need the user's input
- High-level status updates at natural milestones
- Errors or blockers that change the plan
If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations.

# Tone and style
- Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.
- Your responses should be short and concise.
- When referencing specific functions or pieces of code include the pattern file_path:line_number to allow the user to easily navigate to the source code location.
- Do not use a colon before tool calls.

# Chunked Generation & Lazy Coding Prevention (STRICT)
- You are strictly FORBIDDEN from using placeholders like `// TODO`, `pass`, `$(cat secret.txt)`, `[Insert code here]`.
- You MUST write complete, full implementations for all functions.
- If you use placeholders, the system will detect it and reject your turn via Physical Blockers in your Write/Append tools.
- NEVER try to `Write` a massive file (like a large code file or a huge markdown plan) in a single tool call. You will hit token limits and generate lazy code.
- Instead, use the `Append` tool to write large documents/plans chapter by chapter over multiple turns.
- For code editing, DO NOT use `Write` to rewrite an existing file. You MUST use `Replace` or `ReplaceBlock` to perform surgical edits (multi-patching).

# Planning Mode Instructions
When in /plan mode or asked to create a plan:
1. FIRST: Read the project structure using Glob and Read tools. Understand what already exists.
2. SECOND: Analyze the codebase — read key files, understand the architecture, dependencies, and patterns.
3. THIRD: Write an EXTREMELY DETAILED, EXHAUSTIVE, ACTIONABLE plan that references actual files and code in the project.
4. You MUST format the plan using EXACTLY this markdown template. Do not skip any sections. Do not summarize.

   ```markdown
   # [Project Name] Master Plan

   ## Phase 1: [Phase Name]
   ### Task 1.1: [Specific Task Name]
   **Target Files**:
   - `[exact/file/path.ext]`
   **Dependencies/Commands**:
   - `npm install xyz` or `cargo add xyz`
   **Implementation Details**:
   [Write exact code snippets, full function signatures, complete DB schemas, and exact logic here. This MUST NOT be a summary. It must be actual code and technical specs.]
   **Checklist**:
   - [ ] [Micro-step 1]
   - [ ] [Micro-step 2]

   ### Task 1.2: [Next Task]
   ... (Repeat this strict structure for EVERY feature in the project)
   ```

5. After writing the plan, use `TaskCreate` to register the tasks in the system state machine.

# QA Verification Requirement
- BEFORE you output TASK_COMPLETE to finish the user's request, you MUST invoke the `InvokeQA` tool.
- The QA Agent will test your code. If it returns VERDICT: FAIL, you must fix the bugs before completing.

When you have completely fulfilled the user's request and have no more tools to run, output the word TASK_COMPLETE.
"""

OS_INSTRUCTIONS_WINDOWS = """WINDOWS-SPECIFIC RULES:
- Use backslash (\\) for file paths in Bash commands, or use forward slash (/) which also works on Windows.
- Use PowerShell or cmd syntax: `mkdir .nimcode\\plans` (NOT `mkdir -p .nimcode/plans`).
- Use `type` instead of `cat`, `dir` instead of `ls`, `copy` instead of `cp`.
- Use `python` instead of `python3`.
- For creating nested directories, use: `mkdir .nimcode\\plans 2>nul` or `New-Item -ItemType Directory -Force -Path .nimcode\\plans`
- DO NOT use Unix-only commands like chmod, grep (use findstr), sed, awk.
"""

OS_INSTRUCTIONS_UNIX = """UNIX-SPECIFIC RULES:
- Use forward slash (/) for file paths.
- Use standard Unix commands: mkdir -p, cat, ls, cp, chmod.
- Use `python3` if `python` is not available.
"""


def _build_system_prompt(cwd: str) -> str:
    """Builds the system prompt with OS-aware instructions."""
    os_name = platform.system()
    if os_name == "Windows":
        shell_info = "PowerShell / cmd.exe"
        os_specific = OS_INSTRUCTIONS_WINDOWS
    else:
        shell_info = "bash / zsh"
        os_specific = OS_INSTRUCTIONS_UNIX

    return SYSTEM_PROMPT_TEMPLATE.format(
        os_name=os_name,
        shell_info=shell_info,
        cwd=cwd,
        os_specific_instructions=os_specific,
    )


class Agent:
    def __init__(self, api_key: str, model: str = None, max_turns: int = None, permission_mode: PermissionMode = PermissionMode.DEFAULT, max_tokens: int = None):
        # Load global settings
        self.settings = load_settings()
        self.model = model or self.settings.get("model", "deepseek-ai/deepseek-v4-pro")
        api_base_url = self.settings.get("api_base_url", "https://integrate.api.nvidia.com/v1")
        self.client = NimClient(
            api_key=api_key, 
            base_url=api_base_url, 
            model=self.model,
            timeout=self.settings.get("timeout_llm", 120.0),
            max_retries=self.settings.get("max_retries", 15),
            retry_base_delay=self.settings.get("retry_base_delay", 2.0),
            retry_max_delay=self.settings.get("retry_max_delay", 60.0),
        )
        
        # Initialize MCP Manager
        self.mcp = MCPManager(self.settings)
        
        # Stuck-Loop Breaker State
        self.tool_error_counts = {}
        
        # Build OS-aware system prompt
        cwd = os.getcwd()
        final_prompt = _build_system_prompt(cwd) + self.mcp.get_system_prompt_additions()
        
        # Load skills if present
        skills_dir = os.path.join(cwd, ".nimcode", "skills")
        if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
            loaded_skills = []
            for filename in os.listdir(skills_dir):
                if filename.endswith(".md"):
                    with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                        loaded_skills.append(f"--- SKILL: {filename} ---\n{f.read()}\n")
            if loaded_skills:
                final_prompt += "\n\nCRITICAL USER SKILLS & GUIDELINES:\n" + "\n".join(loaded_skills)
                logger.info(f"Loaded {len(loaded_skills)} custom skills from {skills_dir}")
                
        # Active Plan Context
        active_plan_path = os.path.join(cwd, ".nimcode", "active_plan.txt")
        if os.path.exists(active_plan_path):
            try:
                with open(active_plan_path, "r", encoding="utf-8") as f:
                    plan_file = f.read().strip()
                if plan_file:
                    final_prompt += f"\n\nCURRENT ACTIVE PLAN:\nThe user has set '{plan_file}' as the active implementation plan. You MUST read this plan from the file system and follow its step-by-step instructions for your current coding tasks."
            except Exception as e:
                logger.warning(f"Failed to read active plan: {e}")
                
        # Git context
        if os.path.exists(".git"):
            import subprocess
            try:
                branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
                status = subprocess.check_output(["git", "status", "-s"], text=True).strip()
                final_prompt += f"\n\nGIT CONTEXT:\nBranch: {branch}\nUncommitted changes:\n{status if status else 'None'}"
            except Exception as e:
                logger.error(f"Failed to load git context: {e}")

        # Context Injection (Anti-Amnesia RAG)
        try:
            # 1. Directory Tree
            tree_output = ToolRegistry._execute_read_architecture(".", cwd)
            if len(tree_output) > 2000:
                tree_output = tree_output[:2000] + "\n... [TRUNCATED]"
            final_prompt += f"\n\nPROJECT DIRECTORY STRUCTURE:\n{tree_output}"
            
            # 2. Schema Injection
            schema_files = ["schema.sql", "models.py", "prisma/schema.prisma", "db.py"]
            schema_contents = []
            for sf in schema_files:
                sf_path = os.path.join(cwd, sf)
                if os.path.exists(sf_path):
                    with open(sf_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if len(content) > 3000:
                            content = content[:3000] + "\n... [TRUNCATED]"
                        schema_contents.append(f"--- {sf} ---\n{content}")
                        
            if schema_contents:
                final_prompt += "\n\nCRITICAL DATABASE SCHEMAS:\n" + "\n".join(schema_contents)
        except Exception as e:
            logger.error(f"Failed to inject semantic context: {e}")

        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": final_prompt}
        ]
        
        # Use config values with parameter overrides
        cfg_max_turns = self.settings.get("max_turns", 200)
        self.max_turns = max_turns if max_turns is not None else (0 if cfg_max_turns == 0 else cfg_max_turns)
        
        cfg_max_tokens = self.settings.get("max_tokens", 120000)
        effective_max_tokens = max_tokens if max_tokens is not None else cfg_max_tokens
        self.memory = MemoryManager(max_tokens=effective_max_tokens)
        
        self.permission_engine = PermissionEngine(mode=permission_mode)

    def _session_history_path(self) -> str:
        """Path for serialized session history.

        Uses a fresh '.nimcode/sessions/' subdir — NOT '.nimcode/history/' — because
        repl.py's PromptSession already uses '.nimcode/history' as a *file* for
        prompt_toolkit FileHistory. A path cannot be both a file and a directory:
        trying to makedirs('.nimcode/history') while FileHistory treats it as a file
        raises NotADirectoryError, which save_history's try/except would silently
        swallow (re-breaking --resume). 'sessions' is collision-free. This also keeps
        session JSON separate from NIMCODE.md, the human-readable log appended by
        MemoryManager.log_to_nimcode_md — fixing the original Bug B (two producers
        overwriting each other -> JSONDecodeError on load)."""
        return os.path.join(os.getcwd(), ".nimcode", "sessions", "session.json")

    def save_history(self):
        """Saves current conversation (machine-readable JSON) to .nimcode/sessions/session.json."""
        try:
            import json
            path = self._session_history_path()
            # Ensure the parent dir exists (handles one-shot `nimcode "prompt"` and
            # `--resume` paths that don't go through the REPL's .nimcode bootstrap).
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.messages, f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_history(self):
        """Loads conversation from .nimcode/sessions/session.json (if present)."""
        try:
            import json
            path = self._session_history_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.messages = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    async def _stream_response(self) -> str:
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.console import Console
        
        c = Console()
        response_text = ""
        code_theme = self.settings.get("theme", "monokai")
        
        first_chunk = None
        
        with c.status("[bold cyan]🧠 NimCode is thinking...[/bold cyan]", spinner="dots"):
            iterator = self.client.chat(self.messages).__aiter__()
            try:
                first_chunk = await iterator.__anext__()
            except StopAsyncIteration:
                pass
            except KeyboardInterrupt:
                c.print("\n[yellow]Generation interrupted before starting.[/yellow]")
                return ""
                
        if first_chunk is None:
            return ""
            
        response_text = first_chunk
        
        with Live(Markdown(response_text, code_theme=code_theme), console=c, refresh_per_second=15) as live:
            try:
                async for chunk in iterator:
                    response_text += chunk
                    
                    display_text = response_text
                    
                    show_think = self.settings.get("show_thinking", True)
                    import re
                    def style_think(match):
                        if not show_think: return ""
                        content = match.group(1).strip()
                        if not content: return ""
                        return "\n".join(f"> *{line}*" for line in content.split('\n'))
                        
                    display_text = re.sub(r'<think>(.*?)</think>', style_think, display_text, flags=re.DOTALL)
                    
                    if "<think>" in display_text and "</think>" not in display_text:
                        parts = display_text.split("<think>", 1)
                        content = parts[1].strip()
                        if not show_think:
                            display_text = parts[0]
                        elif content:
                            display_text = parts[0] + "\n".join(f"> *{line}*" for line in content.split('\n'))
                        else:
                            display_text = parts[0]
                            
                    tool_tag_idx = display_text.find("<tool_call")
                    if tool_tag_idx != -1:
                        display_text = display_text[:tool_tag_idx] + "\n\n*[dim]⚙️ Preparing tool execution...[/dim]*"
                        
                    live.update(Markdown(display_text, code_theme=code_theme))
            except KeyboardInterrupt:
                live.update(Markdown(response_text + "\n\n*[yellow]Stream interrupted by user.[/yellow]*", code_theme=code_theme))
                c.print("\n[yellow]Generation interrupted.[/yellow]")
                
        # Approximate Token Tracker Update
        est_tokens = len(response_text) // 4
        if not hasattr(self, "session_tokens"):
            self.session_tokens = 0
        self.session_tokens += est_tokens
        
        # Approximate cost based on 70B typical rates ($3/1M tokens)
        cost = (self.session_tokens / 1000000) * 3.0
        c.print(f"[dim]Output est. tokens: {est_tokens} | Session Cost: ~${cost:.4f}[/dim]")
        
        # Context usage warning
        import json
        total_context_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        total_est_tokens = total_context_chars // 4
        from .model_registry import get_context_window
        max_context = get_context_window(self.model)
        if total_est_tokens > max_context * 0.8:
            c.print("[bold yellow]⚠️ Context window is over 80% full. Consider running /compact or /clear.[/bold yellow]")
            
        return response_text

    async def run_headless(self, query: str, max_turns: int = 5) -> str:
        """Runs the agent without terminal streaming, useful for background tasks."""
        self.messages.append({"role": "user", "content": query})
        turn = 0
        from .tools import ToolRegistry
        while turn < max_turns:
            turn += 1
            try:
                # Build a combined prompt from messages for one-shot call
                combined = "\n".join(f"{m['role'].upper()}: {m.get('content','')}" for m in self.messages)
                response_text = await self.client.chat_one_shot(combined)
            except Exception as e:
                return f"Subagent error: {e}"
                
            self.messages.append({"role": "assistant", "content": response_text})
            
            tool_calls = self.parser.parse(response_text)
            if not tool_calls:
                return response_text # Task complete
                
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool")
                if not tool_name: continue
                try:
                    result = ToolRegistry.execute(tool_call)
                except Exception as e:
                    result = str(e)
                self.messages.append({"role": "user", "content": f"Tool {tool_name} returned:\n{result}"})
                
        return "Subagent reached max turns before completing."

    async def _distill_memory(self) -> list:
        system_msg = dict(self.messages[0])
        recent_msgs = self.messages[-4:] if len(self.messages) > 4 else self.messages[1:]
        old_msgs = self.messages[1:-4] if len(self.messages) > 4 else []
        
        if not old_msgs:
            return self.messages
            
        summary_prompt = "You are a summarization AI. Please summarize the following conversation concisely. Focus on the final state, any completed goals, and any context needed for the next steps:\n\n"
        
        existing_summary_marker = "\n\n[PREVIOUS MEMORY SUMMARY]\n"
        if existing_summary_marker in system_msg["content"]:
            parts = system_msg["content"].split(existing_summary_marker, 1)
            system_msg["content"] = parts[0]
            summary_prompt += f"Previous summary to include:\n{parts[1]}\n\n"
            
        for m in old_msgs:
            summary_prompt += f"{m['role'].upper()}: {str(m['content'])[:500]}...\n"
            
        try:
            summary = await self.client.chat_one_shot(summary_prompt)
            system_msg["content"] += f"{existing_summary_marker}{summary}"
            return [system_msg] + recent_msgs
        except Exception as e:
            logger.error(f"Distillation failed: {e}")
            return self.messages

    async def run(self, initial_prompt: str = None) -> None:
        """Main execution loop for NimCode agent."""
        if hasattr(self.mcp, "connect_all"):
            await self.mcp.connect_all()
            
        if initial_prompt:
            self.messages.append({"role": "user", "content": initial_prompt})
        
        cwd = os.getcwd()
        
        # Git Safeguard Stash
        import subprocess
        if os.path.exists(os.path.join(cwd, ".git")):
            try:
                subprocess.run(["git", "stash", "push", "-u", "-m", "nimcode_safeguard_before_run"], cwd=cwd, capture_output=True)
                from rich.console import Console
                Console().print("[dim]🔒 Local changes stashed as 'nimcode_safeguard_before_run'. Agent rollback is armed.[/dim]")
            except:
                pass
        turn = 0
        while self.max_turns == 0 or turn < self.max_turns:
            turn += 1
            logger.info(f"--- Turn {turn} ---")
            
            # Plan-Drift Radar
            if turn > 0 and turn % 15 == 0:
                self.messages.append({
                    "role": "user",
                    "content": "🧭 PLAN RADAR: You have been running for 15 turns. Please read '.nimcode/active_plan.txt' (if it exists) and verify you are strictly following the current phase. If you have drifted, return to the main objective immediately."
                })
            
            # Compact context before calling API
            from rich.console import Console
            if self.memory.count_messages_tokens(self.messages) > self.memory.max_tokens:
                logger.info("Context full. Distilling memory via LLM...")
                Console().print("[dim italic]🧠 Context full. Distilling memory into a summary to save tokens...[/dim italic]")
                self.messages = await self._distill_memory()
            
            # We don't pass tools to the native API for fallback mode.
            # We expect the model to output <tool_call> block in the content.
            full_content = ""
            try:
                full_content = await self._stream_response()
            except Exception as e:
                logger.error(f"Error calling NIM API: {e}")
                break
            
            self.messages.append({"role": "assistant", "content": full_content})
            
            # Anti-Laziness Interceptor
            import re
            lazy_patterns = [r"//\s*TODO", r"#\s*TODO", r"\$\(cat", r"\[Insert", r"\[Your code", r"pass\s*#"]
            lazy_detected = False
            for pat in lazy_patterns:
                if re.search(pat, full_content, re.IGNORECASE):
                    lazy_detected = True
                    break
                    
            if lazy_detected:
                logger.warning("Agent attempted to use placeholder code. Rejecting turn.")
                from rich.console import Console
                Console().print("[bold red]🚨 ANTI-LAZINESS SYSTEM TRIGGERED! Agent tried to use placeholders. Forcing retry.[/bold red]")
                self.messages.append({
                    "role": "user",
                    "content": "ERROR: You violated the ANTI-LAZINESS POLICY by using placeholders, TODOs, or mock strings. You must write the REAL, COMPLETE logic. Re-do this action properly."
                })
                continue
            
            # Log turn to NIMCODE.md
            try:
                # We log the user's latest prompt, or the tool output
                last_user_msg = self.messages[-2].get("content", "") if len(self.messages) > 1 else ""
                MemoryManager.log_to_nimcode_md(turn, last_user_msg, full_content, cwd)
            except Exception as e:
                logger.error(f"Failed to log to NIMCODE.md: {e}")
            
            if "TASK_COMPLETE" in full_content:
                from .task_manager import TaskManager
                tm = TaskManager()
                incomplete = [t for t in tm.get_all_tasks() if t.get("status") in ("pending", "in_progress")]
                
                if incomplete:
                    logger.warning("Agent attempted TASK_COMPLETE but tasks are incomplete.")
                    from rich.console import Console
                    Console().print(f"[bold red]🚨 PHYSICAL BLOCK: Agent tried to exit but {len(incomplete)} tasks are still pending/in_progress. Forcing retry.[/bold red]")
                    self.messages.append({
                        "role": "user",
                        "content": f"SYSTEM ERROR: You attempted to use TASK_COMPLETE, but you still have {len(incomplete)} unfinished tasks. You MUST use tools to complete all tasks before finishing. Please continue working."
                    })
                    continue
                    
                qa_log = os.path.join(cwd, ".nimcode", "qa_results.txt")
                import os as _os
                if not os.path.exists(qa_log) and not _os.environ.get("PYTEST_CURRENT_TEST"):
                    logger.warning("Agent attempted TASK_COMPLETE without running InvokeQA.")
                    from rich.console import Console
                    Console().print("[bold red]🚨 PHYSICAL BLOCK: Agent tried to exit without running InvokeQA. Forcing retry.[/bold red]")
                    self.messages.append({
                        "role": "user",
                        "content": "SYSTEM ERROR: You attempted to use TASK_COMPLETE without running the `InvokeQA` tool. You MUST run InvokeQA to verify your work before exiting."
                    })
                    continue
                    
                logger.info("Agent finished task.")
                break

            try:
                prose, tool_calls = LenientParser.process_model_response(full_content)
                
                if not tool_calls:
                    # Model responded with plain text but didn't say TASK_COMPLETE.
                    if "[Error: Model API returned" in full_content or "[Error communicating with" in full_content:
                        break
                        
                    self.messages.append({"role": "user", "content": "Please continue. Use a tool or output TASK_COMPLETE."})
                    continue
                    
                # We execute the first tool call (ignoring others if it hallucinated multiple)
                tool_call = tool_calls[0]
                tool_name = tool_call.get("tool", "Unknown")
                
                logger.info(f"Checking permissions for tool: {tool_name}")
                if not self.permission_engine.check_permission(tool_call):
                    self.messages.append({
                        "role": "user",
                        "content": f"User explicitly denied permission to execute {tool_name}. Please choose another approach."
                    })
                    continue

                logger.info(f"Running tool: {tool_name}")
                from rich.console import Console
                c = Console()
                try:
                    with c.status(f"[bold cyan]⚙️ Executing {tool_name}...[/bold cyan]", spinner="bouncingBar"):
                        if not ToolRegistry.get_tool_schema(tool_name):
                            # Attempt MCP
                            try:
                                mcp_result = await self.mcp.call_tool_by_name(tool_name, tool_call.get("args", {}))
                                # mcp_result.content is a list of CallToolResult objects
                                result = "\n".join([str(item.text) for item in getattr(mcp_result, 'content', []) if hasattr(item, 'text')])
                                if not result:
                                    result = str(mcp_result)
                            except Exception as e:
                                result = f"Error executing MCP tool {tool_name}: {e}"
                        else:
                            result = ToolRegistry.execute(tool_call)
                            
                        # Auto-Linting & Diff Printing
                        if tool_name in ["Write", "Edit", "Replace", "ReplaceBlock"] and "Error" not in result:
                            if "Diff:\n" in result:
                                parts = result.split("Diff:\n", 1)
                                diff_text = parts[1]
                                from rich.syntax import Syntax
                                c.print(Syntax(diff_text, "diff", theme="monokai", background_color="default"))
                                
                            file_path = tool_call.get("args", {}).get("file_path", "")
                            if file_path.endswith(".py"):
                                import subprocess
                                try:
                                    t_fmt = self.settings.get("timeout_format", 10)
                                    t_fmt = None if t_fmt == 0 else t_fmt
                                    subprocess.run(["black", "-q", file_path], capture_output=True, timeout=t_fmt)
                                    lint = subprocess.run(["flake8", "--select=E9,F821,F822,F823", file_path], capture_output=True, text=True, timeout=t_fmt)
                                    if lint.returncode != 0:
                                        import sys
                                        if sys.stdin.isatty():
                                            from rich.prompt import Confirm
                                            c.print(f"\n[bold yellow]Linter found errors in {file_path}:[/bold yellow]\n{lint.stdout}")
                                            if Confirm.ask("Would you like to auto-fix these errors?"):
                                                result += f"\n\nAuto-Linter found errors:\n{lint.stdout}\nPlease fix them."
                                                c.print(f"[bold red]Auto-fixing...[/bold red]")
                                            else:
                                                c.print("[dim]Ignoring linter errors.[/dim]")
                                        else:
                                            result += f"\n\nAuto-Linter found errors:\n{lint.stdout}\nPlease fix them."
                                except Exception as e:
                                    pass
                            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                                import subprocess
                                try:
                                    t_fmt = self.settings.get("timeout_format", 10)
                                    t_fmt = None if t_fmt == 0 else t_fmt
                                    subprocess.run(["npx", "--yes", "prettier", "--write", file_path], capture_output=True, timeout=t_fmt)
                                    # Basic syntax check for JS
                                    if file_path.endswith(".js"):
                                        lint = subprocess.run(["node", "--check", file_path], capture_output=True, text=True, timeout=t_fmt)
                                        if lint.returncode != 0:
                                            result += f"\n\nAuto-Linter found errors:\n{lint.stderr}\nPlease fix them."
                                except Exception:
                                    pass
                            elif file_path.endswith(".go"):
                                import subprocess
                                try:
                                    t_fmt = self.settings.get("timeout_format", 10)
                                    t_fmt = None if t_fmt == 0 else t_fmt
                                    subprocess.run(["go", "fmt", file_path], capture_output=True, timeout=t_fmt)
                                    lint = subprocess.run(["go", "vet", file_path], capture_output=True, text=True, timeout=t_fmt)
                                    if lint.returncode != 0:
                                        result += f"\n\nAuto-Linter found errors:\n{lint.stderr}\nPlease fix them."
                                except Exception:
                                    pass
                except KeyboardInterrupt:
                    c.print("\n[yellow]Tool execution interrupted by user.[/yellow]")
                    result = "Tool execution was interrupted by the user via Ctrl+C. Ask the user what to do next."
                
                # Print tool result preview for transparency
                if tool_name not in ["Write", "Edit"] and result:
                    preview = str(result)
                    
                    # Try to parse as JSON for Collapsible UI
                    import json
                    try:
                        parsed_json = json.loads(preview)
                        if isinstance(parsed_json, (dict, list)):
                            formatted_json = json.dumps(parsed_json, indent=2)
                            if len(formatted_json) > 800:
                                formatted_json = formatted_json[:800] + f"\n\n... [dim]({len(formatted_json)-800} chars omitted)[/dim]"
                            preview = formatted_json
                    except json.JSONDecodeError:
                        # Rich Table Rendering for Tabular Data
                        if ("\t" in preview or preview.count(",") > 5) and "\n" in preview:
                            from rich.table import Table
                            lines = preview.strip().split("\n")
                            if 2 <= len(lines) <= 50:
                                delim = "\t" if "\t" in lines[0] else ","
                                headers = lines[0].split(delim)
                                table = Table(*headers)
                                valid_table = True
                                for row in lines[1:]:
                                    cols = row.split(delim)
                                    if len(cols) == len(headers):
                                        table.add_row(*cols)
                                    else:
                                        valid_table = False
                                        break
                                if valid_table:
                                    preview = table
                        
                        if isinstance(preview, str) and len(preview) > 500:
                            preview = preview[:500] + f"\n\n[dim]... (truncated {len(preview) - 500} chars)[/dim]"
                    
                    from rich.panel import Panel
                    c.print(Panel(preview, title=f"Output: {tool_name}", border_style="dim", padding=(0, 1)))

                # Stuck-Loop Breaker
                is_error = False
                if isinstance(result, str) and ("Error" in result or "Auto-Linter found errors:" in result or "Traceback" in result):
                    is_error = True
                    
                if is_error:
                    error_hash = hash(tool_name + str(result)[:200])
                    self.tool_error_counts[error_hash] = self.tool_error_counts.get(error_hash, 0) + 1
                    
                    if self.tool_error_counts[error_hash] >= 3:
                        from rich.console import Console
                        Console().print("[bold red]🚨 STUCK-LOOP BREAKER TRIGGERED! Forcing agent to change strategy.[/bold red]")
                        
                        # Git Rollback Attempt
                        rollback_msg = ""
                        try:
                            import subprocess
                            pass
                            if os.path.exists(os.path.join(cwd, ".git")):
                                Console().print("[bold yellow]🔄 Executing automated Git Rollback to break loop...[/bold yellow]")
                                subprocess.run(["git", "reset", "--hard"], cwd=cwd, capture_output=True)
                                subprocess.run(["git", "clean", "-fd"], cwd=cwd, capture_output=True)
                                rollback_msg = "\n\n🚨 GIT ROLLBACK EXECUTED: Your working directory has been reset to the last commit to break you out of this error loop. All broken code you wrote recently has been WIPED. Stop repeating the same mistake."
                        except:
                            pass

                        self.messages.append({
                            "role": "user", 
                            "content": f"Tool {tool_name} returned:\n{result}\n\n🚨 SYSTEM OVERRIDE: You have triggered this exact error 3 times in a row! DO NOT repeat the same action. Use GetCodeOutline, Read, or grep to understand what is wrong, or ask the user for help.{rollback_msg}"
                        })
                        self.tool_error_counts[error_hash] = 0
                    else:
                        self.messages.append({
                            "role": "user", 
                            "content": f"Tool {tool_name} returned:\n{result}"
                        })
                else:
                    self.messages.append({
                        "role": "user", 
                        "content": f"Tool {tool_name} returned:\n{result}"
                    })

            except Exception as e:
                logger.error(f"Error parsing/executing tool: {e}")
                err_str = str(e)
                if "ToolError:" in err_str or "SecretScanner" in err_str or "Validation Error" in err_str:
                    msg = f"Tool {tool_name if 'tool_name' in locals() else 'Unknown'} failed with error: {err_str}\n\n🚨 PHYSICAL BLOCKER: You MUST open a <think> block in your next response to analyze why this failed and how to recover before trying again."
                else:
                    msg = f"Your tool call was malformed or failed: {e}. Please fix the JSON syntax and try again."
                self.messages.append({
                    "role": "user", 
                    "content": msg
                })
        
        if turn >= self.max_turns:
            logger.warning(f"Max turns ({self.max_turns}) reached.")
        
        self.save_history()

