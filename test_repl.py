import asyncio
from unittest.mock import patch, MagicMock
from nimcode.agent import Agent

async def main():
    agent = Agent(api_key="mock")
    
    # Mock the prompt_toolkit session
    class MockSession:
        def __init__(self, *args, **kwargs):
            self.prompts = [
                "/plan",
                "/code",
                "/compact",
                "/clear",
                "/exit"
            ]
            self.idx = 0
            
        async def prompt_async(self, *args, **kwargs):
            if self.idx < len(self.prompts):
                val = self.prompts[self.idx]
                self.idx += 1
                print(f"Mocking user input: {val}")
                return val
            return "/exit"
            
    with patch("prompt_toolkit.PromptSession", return_value=MockSession()):
        await agent.start_repl()
        
    print("REPL loop executed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
