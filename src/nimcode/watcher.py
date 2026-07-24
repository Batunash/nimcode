import os
import threading
import time
import logging
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class LiveSyncHandler(FileSystemEventHandler):
    def __init__(self, agent):
        self.agent = agent
        self.last_sync = 0
        self.debounce_seconds = 2.0

    def on_modified(self, event):
        self._handle_event(event)
        
    def on_created(self, event):
        self._handle_event(event)

    def _handle_event(self, event):
        if event.is_directory:
            return
            
        if not event.src_path.endswith(".py"):
            return
            
        # Ignore our own cache/log directories
        if ".nimcode" in event.src_path or "__pycache__" in event.src_path:
            return

        now = time.time()
        if now - self.last_sync > self.debounce_seconds:
            self.last_sync = now
            self._trigger_sync(event.src_path)
            
    def _trigger_sync(self, path):
        try:
            from .repo_map import RepoMapper
            mapper = RepoMapper(os.getcwd())
            new_map = mapper.generate_map()
            
            # Find the system prompt (always messages[0])
            if not self.agent.messages or self.agent.messages[0]["role"] != "system":
                return
                
            sys_content = self.agent.messages[0]["content"]
            
            # Replace the old repo map block
            pattern = r"--- REPOSITORY MAP ---\n.*?\n----------------------\n"
            replacement = f"--- REPOSITORY MAP ---\n{new_map}\n----------------------\n"
            
            if re.search(pattern, sys_content, re.DOTALL):
                new_sys_content = re.sub(pattern, replacement, sys_content, flags=re.DOTALL)
                self.agent.messages[0]["content"] = new_sys_content
                logger.info(f"Live Sync: Repo map updated due to changes in {path}")
        except Exception as e:
            logger.error(f"Live Sync error: {e}")

class WorkspaceWatcher:
    def __init__(self, agent, root_dir="."):
        self.agent = agent
        self.root_dir = os.path.abspath(root_dir)
        self.observer = None
        
    def start(self):
        try:
            event_handler = LiveSyncHandler(self.agent)
            self.observer = Observer()
            self.observer.schedule(event_handler, self.root_dir, recursive=True)
            self.observer.start()
            logger.info("Workspace Watcher started for Live Sync.")
        except Exception as e:
            logger.error(f"Failed to start workspace watcher: {e}")
            
    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
