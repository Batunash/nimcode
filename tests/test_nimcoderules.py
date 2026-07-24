import os
from nimcode.agent import Agent

def test_nimcoderules_loaded(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    monkeypatch.chdir(cwd)
    
    with open(os.path.join(cwd, ".nimcoderules"), "w") as f:
        f.write("RULE: ALWAYS USE TYPES")
        
    agent = Agent(api_key="dummy")
    assert "RULE: ALWAYS USE TYPES" in agent.messages[0]["content"]

def test_nimcoderules_not_loaded_if_missing(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    monkeypatch.chdir(cwd)
    
    agent = Agent(api_key="dummy")
    assert "PROJECT-SPECIFIC RULES" not in agent.messages[0]["content"]
