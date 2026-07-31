import os
import tempfile
import pytest
from nimcode.task_manager import TaskManager

def test_task_manager_lifecycle():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Task manager uses the cwd implicitly for .nimcode
        tm = TaskManager(workspace_dir=temp_dir)
        
        # Test Create
        res = tm.create_task("1", "Setup DB", "Configure postgres")
        assert "created successfully" in res
        
        # Test List
        tasks = tm.list_tasks()
        assert "1: Setup DB" in tasks
        assert "[ ]" in tasks
        
        # Test Update to in_progress
        res = tm.update_task_status("1", "in_progress")
        assert "updated" in res.lower()
        
        # List again
        tasks = tm.list_tasks()
        assert "[/]" in tasks
        
        # Test Update to completed
        res = tm.update_task_status("1", "completed")
        assert "updated" in res.lower()
        
        tasks = tm.list_tasks()
        assert "[x]" in tasks
        
        # Test invalid status
        res = tm.update_task_status("1", "invalid_status")
        assert "Error" in res or "Invalid" in res

def test_task_manager_linearity():
    with tempfile.TemporaryDirectory() as temp_dir:
        tm = TaskManager(workspace_dir=temp_dir)
        tm.create_task("1.1", "Task 1", "Desc")
        tm.create_task("1.2", "Task 2", "Desc")
        
        # Try to start 1.2 before 1.1 is done
        res = tm.update_task_status("1.2", "in_progress")
        assert "Validation Error" in res
        
        # Complete 1.1
        tm.update_task_status("1.1", "completed")
        
        # Now 1.2 should be startable
        res = tm.update_task_status("1.2", "in_progress")
        assert "updated to in_progress" in res
