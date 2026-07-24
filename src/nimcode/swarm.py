import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SwarmCoordinator:
    def __init__(self, api_key: str, model: str, base_url: str = None, is_local: bool = False):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.is_local = is_local

    async def run_swarm(self, task: str) -> str:
        # Prevent circular imports
        from .agent import NimAgent
        
        logger.info(f"Starting Swarm for task: {task}")
        
        # Subagent 1: Researcher
        researcher = NimAgent(api_key=self.api_key, model=self.model)
        researcher.client.is_local = self.is_local
        if self.base_url:
            researcher.client.base_url = self.base_url
        
        researcher.messages[0]["content"] += "\n\nYou are the Researcher subagent. Analyze the task and propose a step-by-step plan. Only use read tools."
        
        # Subagent 2: Coder
        coder = NimAgent(api_key=self.api_key, model=self.model)
        coder.client.is_local = self.is_local
        if self.base_url:
            coder.client.base_url = self.base_url
        coder.messages[0]["content"] += "\n\nYou are the Coder subagent. You will receive a plan and must implement it using write tools."
        
        # Orchestration
        logger.info("Running Researcher...")
        plan = await researcher.run_headless(f"Create a plan for: {task}", max_turns=5)
        
        logger.info("Running Coder with Plan...")
        result = await coder.run_headless(f"Execute this plan:\n{plan}", max_turns=10)
        
        return f"Swarm finished.\n\nPlan:\n{plan}\n\nResult:\n{result}"
