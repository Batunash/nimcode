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

SYSTEM_PROMPT = """You are nimcode, an autonomous AI coding assistant.
You have access to a set of tools to read, write, and execute code.

CRITICAL INSTRUCTION FOR TOOL CALLING:
You must output exactly ONE tool call per turn, formatted exactly as a fenced XML block.
DO NOT use Markdown code blocks for the tool call. DO NOT output multiple tool calls in a single turn.

Format:
<tool_call>
{"tool": "ToolName", "args": {"arg1": "val1"}}
</tool_call>

Available Tools:
- Bash: {"tool": "Bash", "args": {"command": "string"}}
- Read: {"tool": "Read", "args": {"file_path": "string"}}
- Write: {"tool": "Write", "args": {"file_path": "string", "content": "string"}}
- Edit: {"tool": "Edit", "args": {"file_path": "string", "old_string": "string", "new_string": "string"}}
- Glob: {"tool": "Glob", "args": {"pattern": "string"}}
- Grep: {"tool": "Grep", "args": {"query": "string", "directory": "string"}}

Before calling a tool, you may optionally use a <think> block to reason about your plan. This helps you execute complex tasks correctly.
For example:
<think>
I need to check the file contents first to see where the function is defined.
</think>
<tool_call>
{"tool": "Read", "args": {"file_path": "main.py"}}
</tool_call>

Workspace Guidelines:
- When creating plans, store them inside the `.nimcode/plans/` directory (e.g., `.nimcode/plans/dino_game_plan.md`). Create this directory if it doesn't exist.
- When creating or learning new skills/memories, store them as markdown files inside the `.nimcode/skills/` directory.

When you have completely fulfilled the user's request and have no more tools to run, output the word TASK_COMPLETE.
"""

class Agent:
    def __init__(self, api_key: str, model: str = None, max_turns: int = 30, permission_mode: PermissionMode = PermissionMode.DEFAULT, max_tokens: int = 4000):
        # Load global settings
        self.settings = load_settings()
        self.model = model or self.settings.get("model", "meta/llama-3.1-70b-instruct")
        self.client = NimClient(api_key=api_key, model=self.model)
        
        # Initialize MCP Manager
        self.mcp = MCPManager(self.settings)
        
        # Base system prompt
        final_prompt = SYSTEM_PROMPT + self.mcp.get_system_prompt_additions()
        
        # Load skills if present
        skills_dir = os.path.join(os.getcwd(), ".nimcode", "skills")
        if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
            loaded_skills = []
            for filename in os.listdir(skills_dir):
                if filename.endswith(".md"):
                    with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                        loaded_skills.append(f"--- SKILL: {filename} ---\n{f.read()}\n")
            if loaded_skills:
                final_prompt += "\n\nCRITICAL USER SKILLS & GUIDELINES:\n" + "\n".join(loaded_skills)
                logger.info(f"Loaded {len(loaded_skills)} custom skills from {skills_dir}")
                
        # Git context
        if os.path.exists(".git"):
            import subprocess
            try:
                branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
                status = subprocess.check_output(["git", "status", "-s"], text=True).strip()
                final_prompt += f"\n\nGIT CONTEXT:\nBranch: {branch}\nUncommitted changes:\n{status if status else 'None'}"
            except Exception as e:
                logger.error(f"Failed to load git context: {e}")

        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": final_prompt}
        ]
        self.max_turns = max_turns
        self.permission_engine = PermissionEngine(mode=permission_mode)
        self.memory = MemoryManager(max_tokens=max_tokens)

    def save_history(self):
        """Saves current conversation to NIMCODE.md"""
        try:
            import json
            with open("NIMCODE.md", "w", encoding="utf-8") as f:
                json.dump(self.messages, f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_history(self):
        """Loads conversation from NIMCODE.md"""
        try:
            import json
            if os.path.exists("NIMCODE.md"):
                with open("NIMCODE.md", "r", encoding="utf-8") as f:
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
                            
                    tool_tag_idx = display_text.find("<tool_call>")
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
        max_context = 128000  # Assume standard Llama-3.1 128k context for now
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
                response_text = await self.client.chat_one_shot(self.messages)
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
        system_msg = self.messages[0]
        recent_msgs = self.messages[-4:] if len(self.messages) > 4 else self.messages[1:]
        old_msgs = self.messages[1:-4] if len(self.messages) > 4 else []
        
        if not old_msgs:
            return self.messages
            
        summary_prompt = "Please summarize the following conversation concisely. Focus on the final state, any completed goals, and any context needed for the next steps:\n\n"
        for m in old_msgs:
            summary_prompt += f"{m['role'].upper()}: {str(m['content'])[:500]}...\n"
            
        messages = [{"role": "system", "content": "You are a summarization AI."}, {"role": "user", "content": summary_prompt}]
        try:
            summary = await self.client.chat_one_shot(messages)
            system_msg["content"] += f"\n\n[PREVIOUS MEMORY SUMMARY]\n{summary}"
        except Exception as e:
            logger.error(f"Distillation failed: {e}")
            
        return [system_msg] + recent_msgs

    async def run(self, initial_prompt: str = None) -> None:
        """Main execution loop for NimCode agent."""
        if hasattr(self.mcp, "connect_all"):
            await self.mcp.connect_all()
            
        if initial_prompt:
            self.messages.append({"role": "user", "content": initial_prompt})
        
        cwd = os.getcwd()
        turn = 0
        while turn < self.max_turns:
            turn += 1
            logger.info(f"--- Turn {turn} ---")
            
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
            
            # Log turn to NIMCODE.md
            try:
                # We log the user's latest prompt, or the tool output
                last_user_msg = self.messages[-2].get("content", "") if len(self.messages) > 1 else ""
                MemoryManager.log_to_nimcode_md(turn, last_user_msg, full_content, cwd)
            except Exception as e:
                logger.error(f"Failed to log to NIMCODE.md: {e}")
            
            if "TASK_COMPLETE" in full_content:
                logger.info("Agent finished task.")
                break

            try:
                prose, tool_calls = LenientParser.process_model_response(full_content)
                
                if not tool_calls:
                    # Model responded with plain text but didn't say TASK_COMPLETE.
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
                        if tool_name in ["Write", "Edit"] and "Error" not in result:
                            if "Diff:\n" in result:
                                parts = result.split("Diff:\n", 1)
                                diff_text = parts[1]
                                from rich.syntax import Syntax
                                c.print(Syntax(diff_text, "diff", theme="monokai", background_color="default"))
                                
                            file_path = tool_call.get("args", {}).get("file_path", "")
                            if file_path.endswith(".py"):
                                import subprocess
                                try:
                                    subprocess.run(["black", "-q", file_path], capture_output=True)
                                    lint = subprocess.run(["flake8", "--select=E9,F821,F822,F823", file_path], capture_output=True, text=True)
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
                                    subprocess.run(["npx", "prettier", "--write", file_path], capture_output=True)
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

                # We simulate tool messages by adding a user message with the tool result.
                # In native mode this would be a "tool" role message, but for fallback mode, 
                # passing it as a user message makes it explicit.
                self.messages.append({
                    "role": "user", 
                    "content": f"Tool {tool_name} returned:\n{result}"
                })

            except Exception as e:
                logger.error(f"Error parsing/executing tool: {e}")
                self.messages.append({
                    "role": "user", 
                    "content": f"Your tool call was malformed or failed: {e}. Please fix the JSON syntax and try again."
                })
        
        if turn >= self.max_turns:
            logger.warning(f"Max turns ({self.max_turns}) reached.")
        
        self.save_history()

