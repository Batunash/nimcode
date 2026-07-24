import sys
import os
import json
import asyncio
import logging
from .agent import Agent
from .permissions import PermissionMode

logger = logging.getLogger(__name__)

class StdioServer:
    """
    Communicates with the VS Code extension via JSON-RPC over standard input/output.
    Intercepts the Agent's print statements and permission checks to keep IPC clean.
    """
    def __init__(self, agent: Agent):
        self.agent = agent
        # Save original stdout for IPC, redirect normal stdout to os.devnull
        self.ipc_stdout = sys.__stdout__
        sys.stdout = open(os.devnull, 'w')
        
        self.pending_action: asyncio.Future = None

        # Monkey-patch agent permission prompting and output
        self._patch_agent()

    def _patch_agent(self):
        # Override the agent's permission prompter
        original_prompt = self.agent.permission_engine._prompt_user
        
        async def async_prompt_override(tool_call):
            if self.agent.permission_engine.mode == PermissionMode.BYPASS:
                return True
                
            self.send_message({
                "type": "action_required",
                "tool": tool_call.get("tool"),
                "args": tool_call.get("args")
            })
            
            # Wait for VS Code to respond
            self.pending_action = asyncio.Future()
            result = await self.pending_action
            return result
            
        self.agent.permission_engine._prompt_user = async_prompt_override

        # Override stream output to send tokens via IPC instead of stdout
        original_stream = self.agent._stream_response
        
        async def stdio_stream_response():
            self.send_message({"type": "status", "content": "Thinking..."})
            full_content = ""
            async for chunk in self.agent.client.chat_stream(self.agent.messages):
                full_content += chunk
                self.send_message({"type": "chunk", "content": chunk})
            self.send_message({"type": "done"})
            return full_content
            
        self.agent._stream_response = stdio_stream_response

        # Override rich.console.Console.print to capture slash command outputs and general prints
        from rich.console import Console
        original_print = Console.print
        
        def patched_print(console_self, *objects, **kwargs):
            # Try to extract raw string from objects
            text_parts = []
            for obj in objects:
                if isinstance(obj, str):
                    text_parts.append(obj)
                elif hasattr(obj, "__rich_console__") or hasattr(obj, "__rich_measure__"):
                    # For complex rich objects (like Markdown), we could render it to text
                    try:
                        with console_self.capture() as capture:
                            original_print(console_self, obj, **kwargs)
                        text_parts.append(capture.get())
                    except Exception:
                        text_parts.append(str(obj))
                else:
                    text_parts.append(str(obj))
                    
            if text_parts:
                content = " ".join(text_parts)
                # Strip excessive ANSI codes if capture includes them, but we want plain text or markdown
                # For simplicity, just send it to the UI
                self.send_message({"type": "info", "content": content})
                
        Console.print = patched_print

    def send_message(self, message: dict):
        """Send a JSON message to original stdout."""
        try:
            self.ipc_stdout.write(json.dumps(message) + "\n")
            self.ipc_stdout.flush()
        except Exception:
            pass

    async def start(self):
        """Start the stdio listener loop."""
        self.send_message({"type": "info", "content": "NimCode Stdio Server Started"})
        
        async def fetch_and_send_models():
            try:
                models = await self.agent.client.get_available_models()
                self.send_message({"type": "models_list", "models": models, "current": self.agent.model})
            except Exception:
                pass
        asyncio.create_task(fetch_and_send_models())
        
        loop = asyncio.get_running_loop()
        
        while True:
            # Read line from stdin in a non-blocking way if possible
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            try:
                msg = json.loads(line)
                msg_type = msg.get("type")
                
                if msg_type == "prompt":
                    prompt = msg.get("content", "")
                    # Fire and forget the agent run loop so it doesn't block the stdin reader
                    asyncio.create_task(self._run_agent(prompt))
                elif msg_type == "action_response":
                    if self.pending_action and not self.pending_action.done():
                        granted = msg.get("granted", False)
                        self.pending_action.set_result(granted)
                elif msg_type == "clear":
                    self.agent.messages = [self.agent.messages[0]]
                    self.send_message({"type": "info", "content": "Context cleared"})
                elif msg_type == "set_mode":
                    mode = msg.get("mode")
                    if mode in [m.value for m in PermissionMode]:
                        self.agent.permission_engine.mode = PermissionMode(mode)
                        self.send_message({"type": "info", "content": f"Mode changed to {mode}"})
                elif msg_type == "set_model":
                    model = msg.get("model")
                    if model:
                        self.agent.model = model
                        self.agent.client.model = model
                        
                        from .config import save_global_setting
                        save_global_setting("model", model)
                        self.send_message({"type": "info", "content": f"Model changed to {model}"})
                        
            except json.JSONDecodeError:
                self.send_message({"type": "error", "content": "Invalid JSON received"})
            except Exception as e:
                self.send_message({"type": "error", "content": f"Server error: {e}"})

    async def _run_agent(self, prompt: str):
        try:
            await self.agent.run(prompt)
            self.send_message({"type": "agent_finished"})
        except Exception as e:
            self.send_message({"type": "error", "content": f"Agent crashed: {e}"})
