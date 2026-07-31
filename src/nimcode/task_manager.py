import json
import os
import time
from typing import Dict, List, Optional

class Task:
    def __init__(self, task_id: str, subject: str, description: str, status: str = "pending"):
        self.task_id = task_id
        self.subject = subject
        self.description = description
        self.status = status
        self.created_at = time.time()
        self.updated_at = time.time()

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict):
        task = cls(
            task_id=data["task_id"],
            subject=data["subject"],
            description=data["description"],
            status=data.get("status", "pending")
        )
        task.created_at = data.get("created_at", time.time())
        task.updated_at = data.get("updated_at", time.time())
        return task

class TaskManager:
    def __init__(self, workspace_dir: str = ".nimcode"):
        self.workspace_dir = workspace_dir
        self.tasks_file = os.path.join(workspace_dir, "tasks.json")
        self.tasks: Dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self):
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for t_id, t_data in data.items():
                        self.tasks[t_id] = Task.from_dict(t_data)
            except Exception as e:
                print(f"Failed to load tasks: {e}")

    def _save_tasks(self):
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir, exist_ok=True)
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                data = {t_id: t.to_dict() for t_id, t in self.tasks.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save tasks: {e}")

    def create_task(self, task_id: str, subject: str, description: str) -> str:
        if task_id in self.tasks:
            return f"Task {task_id} already exists."
        
        self.tasks[task_id] = Task(task_id, subject, description)
        self._save_tasks()
        return f"Task {task_id} created successfully."

    def update_task_status(self, task_id: str, status: str) -> str:
        if task_id not in self.tasks:
            return f"Task {task_id} not found."
        
        valid_statuses = ["pending", "in_progress", "completed", "failed"]
        if status not in valid_statuses:
            return f"Invalid status: {status}. Must be one of {valid_statuses}."

        if status == "in_progress":
            # Check linearity: all previous tasks must be completed or failed
            for t_id, t in self.tasks.items():
                if t_id == task_id:
                    break
                if t.status not in ["completed", "failed"]:
                    return f"Validation Error: Cannot start task {task_id} because previous task {t_id} is still '{t.status}'. You must complete tasks in order."

        self.tasks[task_id].status = status
        self.tasks[task_id].updated_at = time.time()
        self._save_tasks()
        return f"Task {task_id} status updated to {status}."

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> str:
        if not self.tasks:
            return "No tasks found."
        
        output = []
        for t_id, t in self.tasks.items():
            status_symbol = {
                "pending": "[ ]",
                "in_progress": "[/]",
                "completed": "[x]",
                "failed": "[!]"
            }.get(t.status, "[?]")
            output.append(f"{status_symbol} {t_id}: {t.subject}")
        return "\n".join(output)
