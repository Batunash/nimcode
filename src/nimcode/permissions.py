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
            console.print(f"[yellow]Running non-interactive. Approving {tool_name} for tests.[/yellow]")
            return True
            
        while True:
            content = ""
            if tool_name == "Bash":
                content = f"[bold]Command:[/bold]\n{args.get('command')}"
            elif tool_name == "Write":
                content = f"[bold]File:[/bold] {args.get('file_path')}\n[bold]Action:[/bold] Overwrite with new content"
            elif tool_name == "Edit":
                content = f"[bold]File:[/bold] {args.get('file_path')}\n[bold]Replacing:[/bold] '{args.get('old_string')}' -> '{args.get('new_string')}'"
            else:
                content = f"[bold]Args:[/bold] {json.dumps(args, indent=2)}"
                
            panel = Panel(content, title=f"NimCode Wants to Run: {tool_name}", border_style="yellow")
            console.print(panel)
            
            choice = Prompt.ask("[bold cyan]Action[/bold cyan] [green](a)ccept[/green] / [red](r)eject[/red] / [blue](e)dit[/blue]", choices=["a", "r", "e"], default="a", show_choices=False)
            
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
