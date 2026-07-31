import os
import pytest
from unittest.mock import patch
from nimcode.agents.qa_agent import QAAgent

@patch("nimcode.nim_client.NimClient.chat")
@patch("nimcode.task_manager.TaskManager.get_all_tasks", return_value=[])
def test_qa_agent_verdict_pass(mock_get_tasks, mock_chat):
    # Mocking the async chat function
    async def mock_chat_return(*args, **kwargs):
        return "I have tested the code. VERDICT: PASS"
    mock_chat.side_effect = mock_chat_return

    agent = QAAgent(cwd=".")
    
    # We must patch os.environ to ensure an API key exists to bypass the key check
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "test_key"}):
        result = agent.run("Please verify this implementation")
        assert "QA Agent VERDICT: PASS" in result

@patch("nimcode.nim_client.NimClient.chat")
@patch("nimcode.task_manager.TaskManager.get_all_tasks", return_value=[])
def test_qa_agent_verdict_fail(mock_get_tasks, mock_chat):
    async def mock_chat_return(*args, **kwargs):
        return "The test failed. VERDICT: FAIL"
    mock_chat.side_effect = mock_chat_return

    agent = QAAgent(cwd=".")
    
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "test_key"}):
        result = agent.run("Please verify this implementation")
        assert "QA Agent VERDICT: FAIL" in result
