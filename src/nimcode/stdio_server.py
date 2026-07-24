import sys
import json
import asyncio
import logging
from .agent import Agent
from .config import load_settings

logger = logging.getLogger(__name__)

class StdioServer:
    """
    Communicates with the VS Code extension via JSON-RPC over standard input/output.
    """
    def __init__(self, agent: Agent):
        self.agent = agent

    def send_message(self, message: dict):
        """Send a JSON message to stdout."""
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    async def _mock_stream_response(self, initial_prompt: str):
        """
        Since the regular stream_response expects a terminal, we override the agent's behavior
        for stdio to send chunks back as JSON messages.
        """
        self.agent.messages.append({"role": "user", "content": initial_prompt})
        
        full_response = ""
        try:
            self.send_message({"type": "status", "content": "Thinking..."})
            async for chunk in self.agent.client.chat_stream(self.agent.messages):
                full_response += chunk
                self.send_message({"type": "chunk", "content": chunk})
                
            self.agent.messages.append({"role": "assistant", "content": full_response})
            self.agent.save_history()
            
            self.send_message({"type": "done"})
        except Exception as e:
            self.send_message({"type": "error", "content": str(e)})

    async def start(self):
        """Start the stdio listener loop."""
        self.send_message({"type": "info", "content": "NimCode Stdio Server Started"})
        
        loop = asyncio.get_running_loop()
        
        while True:
            # Read line from stdin in a non-blocking way if possible, or run in executor
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
                    await self._mock_stream_response(prompt)
                elif msg_type == "clear":
                    self.agent.messages = [self.agent.messages[0]]
                    self.send_message({"type": "info", "content": "Context cleared"})
                
            except json.JSONDecodeError:
                self.send_message({"type": "error", "content": "Invalid JSON received"})
            except Exception as e:
                self.send_message({"type": "error", "content": f"Server error: {e}"})
