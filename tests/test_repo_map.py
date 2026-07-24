import os
from nimcode.repo_map import RepoMapper

def test_repo_mapper(tmp_path):
    # Create dummy python files
    file1 = tmp_path / "test1.py"
    file1.write_text("""
class TestClass:
    def method1(self):
        pass
        
def top_level_func():
    pass
""", encoding="utf-8")

    mapper = RepoMapper(root_dir=str(tmp_path))
    repo_map = mapper.generate_map()
    
    assert "FILE: test1.py" in repo_map
    assert "class TestClass:" in repo_map
    assert "def method1(...)" in repo_map
    assert "def top_level_func(...)" in repo_map
