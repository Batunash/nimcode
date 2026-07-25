"""Tests for repo_map module."""
import os
import pytest
import tempfile
from nimcode.repo_map import RepoMapper, _format_size


def test_format_size_bytes():
    assert _format_size(500) == "500B"
    assert _format_size(0) == "0B"


def test_format_size_kb():
    result = _format_size(2048)
    assert "KB" in result


def test_format_size_mb():
    result = _format_size(2 * 1024 * 1024)
    assert "MB" in result


def test_generate_map_basic(tmp_path):
    """Test basic tree generation with files and directories."""
    # Create a simple project structure
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.py").write_text("def helper(): pass")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "app.py").write_text("class App: pass")
    
    mapper = RepoMapper(str(tmp_path))
    result = mapper.generate_map()
    
    assert "main.py" in result
    assert "utils.py" in result
    assert "src" in result
    assert "app.py" in result


def test_generate_map_ignores_pycache(tmp_path):
    """Test that __pycache__ directories are ignored."""
    (tmp_path / "main.py").write_text("x = 1")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-311.pyc").write_bytes(b"bytecode")
    
    mapper = RepoMapper(str(tmp_path))
    result = mapper.generate_map()
    
    assert "main.py" in result
    assert "__pycache__" not in result


def test_generate_map_ignores_node_modules(tmp_path):
    """Test that node_modules is ignored."""
    (tmp_path / "index.js").write_text("console.log('hi')")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "package.json").write_text("{}")
    
    mapper = RepoMapper(str(tmp_path))
    result = mapper.generate_map()
    
    assert "index.js" in result
    assert "node_modules" not in result


def test_generate_map_max_depth(tmp_path):
    """Test that max_depth is respected."""
    # Create a deeply nested structure
    current = tmp_path
    for i in range(10):
        current = current / f"level{i}"
        current.mkdir()
        (current / "file.py").write_text(f"level {i}")
    
    mapper = RepoMapper(str(tmp_path), max_depth=3)
    result = mapper.generate_map()
    
    assert "level0" in result
    assert "level1" in result
    # Deep levels should NOT appear
    assert "level8" not in result


def test_generate_map_empty_dir(tmp_path):
    """Empty directory should still generate valid output."""
    mapper = RepoMapper(str(tmp_path))
    result = mapper.generate_map()
    
    # Should at least have the root directory name
    assert tmp_path.name in result
