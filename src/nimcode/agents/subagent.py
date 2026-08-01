import asyncio
from typing import List, Dict, Any
from nimcode.agent import Agent

class SubAgent:
    def __init__(self, api_key: str, model: str = None):
        from nimcode.model_registry import DEFAULT_CONTEXT_WINDOW
        self.api_key = api_key
        # Use default model or passed in model
        self.model = model or "meta/llama-3.1-8b-instruct"
        # We start a new Agent instance
        self.agent = Agent(api_key=self.api_key, model=self.model)

    async def execute_task(self, task_description: str, target_files: List[str]) -> str:
        """Executes a specific task headlessly and returns the result."""
        prompt = f"TASK: {task_description}\n\nTARGET FILES:\n"
        for f in target_files:
            prompt += f"- {f}\n"
        
        prompt += "\nReturn a summary of what you did when you are finished."
        
        result = await self.agent.run_headless(prompt, max_turns=10)
        return result
