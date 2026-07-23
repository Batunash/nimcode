import asyncio
from unittest.mock import patch
from nimcode.agent import Agent
from nimcode.permissions import PermissionMode

async def main():
    agent = Agent(api_key="mock", permission_mode=PermissionMode.BYPASS)
    
    # We will simulate the model responding with a Bash tool call
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield "I will create a hello.py file and run it using Bash.\n"
            yield "<tool_call>\n"
            yield '{"tool": "Bash", "args": {"command": "echo \\"print(\'Hello NimCode\')\\" > hello.py && python hello.py"}}\n'
            yield "</tool_call>"
        else:
            yield "The file was created and run successfully! TASK_COMPLETE"
            
    agent.client.chat = mock_chat
    
    print("Testing NimCode with mock LLM...")
    await agent.run("Create a python script that says Hello NimCode and run it.")
    
if __name__ == "__main__":
    asyncio.run(main())
