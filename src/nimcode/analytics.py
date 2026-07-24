import sqlite3
import os
import time

class AnalyticsEngine:
    def __init__(self, db_path=None):
        if not db_path:
            global_dir = os.path.expanduser("~/.nimcode")
            os.makedirs(global_dir, exist_ok=True)
            self.db_path = os.path.join(global_dir, "analytics.db")
        else:
            self.db_path = db_path
            
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    cost_usd REAL
                )
            ''')
            conn.commit()

    def log_usage(self, model: str, prompt_tokens: int, completion_tokens: int):
        # Calculate cost based on current NIM pricing (estimated)
        # e.g., $0.50 per 1M prompt, $1.50 per 1M completion for llama3-70b
        cost_usd = (prompt_tokens / 1_000_000) * 0.50 + (completion_tokens / 1_000_000) * 1.50
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO token_usage (timestamp, model, prompt_tokens, completion_tokens, cost_usd) VALUES (?, ?, ?, ?, ?)",
                (time.time(), model, prompt_tokens, completion_tokens, cost_usd)
            )
            conn.commit()

    def get_summary(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total stats
            cursor.execute("SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(cost_usd) FROM token_usage")
            total_stats = cursor.fetchone()
            
            # Today's stats
            today_start = time.time() - (time.time() % 86400) # Start of UTC day approx
            cursor.execute("SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(cost_usd) FROM token_usage WHERE timestamp >= ?", (today_start,))
            today_stats = cursor.fetchone()
            
        return {
            "total": {
                "prompt_tokens": total_stats[0] or 0,
                "completion_tokens": total_stats[1] or 0,
                "cost_usd": total_stats[2] or 0.0
            },
            "today": {
                "prompt_tokens": today_stats[0] or 0,
                "completion_tokens": today_stats[1] or 0,
                "cost_usd": today_stats[2] or 0.0
            }
        }
