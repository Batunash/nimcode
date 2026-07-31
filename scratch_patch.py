import asyncio
from unittest.mock import patch
from nimcode.agent import Agent
from nimcode.task_manager import TaskManager

async def main():
    print("Real tasks:", TaskManager().get_all_tasks())
    
    with patch("nimcode.task_manager.TaskManager.get_all_tasks", return_value=[]):
        print("Patched tasks (direct):", TaskManager().get_all_tasks())
        a = Agent(api_key="test_key")
        print("Patched tasks (via agent):", TaskManager().get_all_tasks())

asyncio.run(main())
