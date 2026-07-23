import re

with open("tests/test_repl.py", "r", encoding="utf-8") as f:
    content = f.read()

agent_fixture = """
@pytest.fixture
def agent():
    with patch("nimcode.agent.NimClient"):
        a = Agent(api_key="test_key")
        a.client.chat_one_shot = AsyncMock(return_value="I am done. TASK_COMPLETE")
        a.client.get_available_models = AsyncMock(return_value=["model1", "model2"])
        a.client.chat = MagicMock()
        return a

def test_repl_properties(agent):"""

content = content.replace("def test_repl_properties(agent):", agent_fixture.strip())

with open("tests/test_repl.py", "w", encoding="utf-8") as f:
    f.write(content)
