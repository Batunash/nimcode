import os
import re
import asyncio
from typing import Optional

class QAAgent:
    def __init__(self, cwd: str = "."):
        self.cwd = cwd

    def run(self, instructions: str) -> str:
        # Check if tasks are completed first (Physical blocker)
        from ..task_manager import TaskManager
        tm = TaskManager()
        incomplete = [t for t in tm.get_all_tasks() if t.get("status") in ("pending", "in_progress")]
        if incomplete:
            return f"VERDICT: FAIL\nYou cannot pass QA. There are still {len(incomplete)} unfinished tasks in tasks.json. Go back and complete them."
            
        # Load API key
        import json
        settings_path = os.path.join(self.cwd, ".nimcode", "settings.json")
        api_key = os.environ.get("NVIDIA_API_KEY")
        model = "deepseek-ai/deepseek-v4-pro"
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    api_key = settings.get("nvidia_api_key", api_key)
                    model = settings.get("default_model", model)
            except:
                pass

        if not api_key:
            return "QA Agent Error: No NVIDIA API key found."

        from ..nim_client import NimClient
        from ..tools import ToolRegistry

        client = NimClient(api_key=api_key, model=model)

        system_prompt = """You are a QA Verification Agent. Your job is to verify that the implementation works by trying to break it.
You MUST test the code using the Bash tool. You are STRICTLY PROHIBITED from modifying the project files (no editing, no writing).

=== REQUIRED STEPS ===
1. Use the Bash tool to run the tests, execute the script, or curl the API.
2. Read the output.
3. If it succeeds, try an edge case or a boundary value.
4. Output your analysis.
5. End your final message with EXACTLY ONE of the following lines:
VERDICT: PASS
VERDICT: FAIL
VERDICT: PARTIAL
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please verify the following implementation:\n{instructions}"}
        ]

        # Basic interaction loop for the QA Agent (max 5 turns)
        for _ in range(5):
            try:
                response = asyncio.run(client.chat(messages))
            except Exception as e:
                return f"QA Agent Error calling NIM API: {e}"

            messages.append({"role": "assistant", "content": response})

            # Check for VERDICT
            if "VERDICT: PASS" in response:
                return "QA Agent VERDICT: PASS\n\n" + response
            elif "VERDICT: FAIL" in response:
                return "QA Agent VERDICT: FAIL\n\n" + response
            elif "VERDICT: PARTIAL" in response:
                return "QA Agent VERDICT: PARTIAL\n\n" + response

            # Check for Tool Calls
            tool_calls = re.findall(r'<tool_call>\s*({.*?})\s*</tool_call>', response, re.DOTALL)
            if not tool_calls:
                # No tool call and no verdict? Ask it to provide a verdict.
                messages.append({"role": "user", "content": "You didn't use a tool or provide a VERDICT. Please use a tool to test, or output VERDICT: PASS / FAIL / PARTIAL."})
                continue

            # Execute the first tool call
            try:
                tool_call = json.loads(tool_calls[0])
                if tool_call.get("tool") != "Bash" and tool_call.get("tool") != "Read":
                    tool_output = "QA Agent is ONLY allowed to use the Bash and Read tools."
                else:
                    tool_output = ToolRegistry.execute(tool_call, self.cwd)
            except Exception as e:
                tool_output = f"Invalid tool call: {e}"

            messages.append({"role": "user", "content": f"Tool Output:\n{tool_output}"})

        return "QA Agent VERDICT: FAIL (Timed out after 5 turns without reaching a conclusion)."
