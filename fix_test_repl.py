import re

with open("tests/test_repl.py", "r", encoding="utf-8") as f:
    content = f.read()

bad_block = """import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from nimcode.repl import NimcodeREPL
from nimcode.agent import Agent
            mock_session.prompt_async = AsyncMock(side_effect=commands)
            with patch("builtins.input", return_value="y"):
                repl = NimcodeREPL(agent)
                try:
                    await repl.start_repl()
                except StopAsyncIteration:
                    pass"""

good_block = """
def test_repl_properties(agent):
    agent.mcp = MagicMock()
    repl = NimcodeREPL(agent)
    assert repl.mcp == agent.mcp

@pytest.mark.asyncio
async def test_repl_coverage_display(agent):
    # Test coverage display calculation
    with patch("coverage.Coverage") as MockCov:
        mock_cov_instance = MockCov.return_value
        mock_cov_instance.report.return_value = 60.5  # middle coverage -> yellow
        
        # we just want to hit start_repl to execute the coverage part
        commands = ["/exit"]
        with patch("prompt_toolkit.PromptSession") as MockSession:
            mock_session = MockSession.return_value
            mock_session.prompt_async = AsyncMock(side_effect=commands)
            with patch("builtins.input", return_value="y"):
                repl = NimcodeREPL(agent)
                try:
                    await repl.start_repl()
                except StopAsyncIteration:
                    pass
"""

if bad_block in content:
    content = content.replace(bad_block, good_block)
else:
    print("bad_block not found in content!")

with open("tests/test_repl.py", "w", encoding="utf-8") as f:
    f.write(content)
