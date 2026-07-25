import typer
import logging
from typing import Dict, Any
from enum import Enum
from rich.console import Console
import sys

logger = logging.getLogger(__name__)
console = Console()

class PermissionMode(str, Enum):
    DEFAULT = "default"  # Prompts for everything (simulated in headless)
    BYPASS = "bypass"    # Allows everything
    AUTO = "auto"        # Allows safe reads, prompts for dangerous actions

class PermissionEngine:
    def __init__(self, mode: PermissionMode = PermissionMode.DEFAULT):
        self.mode = mode
        self.safe_tools = {"Read", "Glob", "Grep"}

    def check_permission(self, tool_call: dict) -> bool:
        """Returns True if permitted, False otherwise."""
        if self.mode == PermissionMode.BYPASS:
            return True
            
        tool_name = tool_call.get("tool")
        
        if self.mode == PermissionMode.AUTO and tool_name in self.safe_tools:
            return True
            
        return self._prompt_user(tool_call)
            
    def _prompt_user(self, tool_call: Dict[str, Any]) -> bool:
        from rich.panel import Panel
        from rich.prompt import Prompt
        import json
        
        tool_name = tool_call.get("tool")
        args = tool_call.get("args", {})
        
        if not sys.stdin.isatty():
            # Non-interactive mode: only auto-approve safe tools + writes.
            # Bash requires explicit opt-in via config.
            from .config import load_settings
            settings = load_settings()
            safe_non_interactive = {"Read", "Glob", "Grep", "Write", "Edit", "ASTReplace"}
            if tool_name in safe_non_interactive:
                return True
            if tool_name == "Bash" and settings.get("allow_bash_non_interactive", False):
                console.print(f"[yellow]Non-interactive: Bash auto-approved via config.[/yellow]")
                return True
            console.print(f"[red]Non-interactive: {tool_name} DENIED (enable 'allow_bash_non_interactive' in settings to allow).[/red]")
            return False
            
        while True:
            content = ""
            if tool_name == "Bash":
                content = f"Command:\n{args.get('command')}"
            elif tool_name == "Write":
                content_lines = len(args.get('content', '').split('\n'))
                content = f"File: [bold cyan]{args.get('file_path')}[/bold cyan]\nAction: Overwrite with [bold green]{content_lines} new lines[/bold green]"
            elif tool_name in ["Edit", "ASTReplace"]:
                import difflib
                import os
                file_path = args.get('file_path', '')
                
                # Default to basic diff summary
                diff_str = ""
                
                if tool_name == "Edit":
                    old_str = args.get('old_string', '')
                    new_str = args.get('new_string', '')
                    diff = list(difflib.unified_diff(old_str.splitlines(keepends=True), new_str.splitlines(keepends=True), fromfile=file_path, tofile=file_path))
                    diff_str = "".join(diff)
                elif tool_name == "ASTReplace":
                    new_code = args.get('code', '')
                    target = args.get('target', '')
                    try:
                        if os.path.exists(file_path):
                            with open(file_path, "r", encoding="utf-8") as f:
                                source = f.read()
                            # We can't perfectly predict ASTReplace diff without parsing, so we just show the replacement
                            diff_str = f"--- ASTReplace target: {target}\n+++ Replacement code:\n{new_code}"
                    except:
                        pass
                
                # Format diff with rich
                from rich.text import Text
                diff_text = Text()
                for line in diff_str.splitlines():
                    if line.startswith("+"):
                        diff_text.append(line + "\n", style="green")
                    elif line.startswith("-"):
                        diff_text.append(line + "\n", style="red")
                    elif line.startswith("@"):
                        diff_text.append(line + "\n", style="cyan")
                    else:
                        diff_text.append(line + "\n")
                        
                content = f"File: [bold cyan]{args.get('file_path')}[/bold cyan]\n"
                console.print(Panel(diff_text, title=f"Diff Preview: {tool_name}"))
            else:
                content = f"Args: {{\n"
                for k, v in args.items():
                    content += f"  \"{k}\": \"{v}\"\n"
                content += "}"
                
            from rich.box import ROUNDED
            panel = Panel(content, title=f"NimCode Wants to Run: {tool_name}", border_style="bright_blue", box=ROUNDED, padding=(0, 1))
            console.print(panel)
            
            # Using prompt toolkit or simple input to avoid rich coloring for exactly matching the trace
            choice = input("Action (a)ccept / (r)eject / (e)dit (a): ").strip().lower()
            if not choice:
                choice = "a"
            
            if choice == "a":
                return True
            elif choice == "r":
                return False
            elif choice == "e":
                from prompt_toolkit import prompt as pt_prompt
                if tool_name == "Bash":
                    new_cmd = pt_prompt("Edit Command: ", default=args.get("command", ""))
                    tool_call["args"]["command"] = new_cmd
                else:
                    new_args_str = pt_prompt("Edit Args (JSON): ", default=json.dumps(args))
                    try:
                        tool_call["args"] = json.loads(new_args_str)
                    except json.JSONDecodeError:
                        console.print("[red]Invalid JSON. Please try again.[/red]")
                        continue
                args = tool_call.get("args", {})
                # Loop repeats and shows the updated panel for final confirmation
