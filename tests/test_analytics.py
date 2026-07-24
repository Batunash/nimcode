import os
import sqlite3
import pytest
from nimcode.analytics import AnalyticsEngine

def test_analytics_engine(tmp_path):
    db_path = os.path.join(tmp_path, "analytics.db")
    engine = AnalyticsEngine(db_path=db_path)
    
    # Initially empty
    summary = engine.get_summary()
    assert summary["total"]["prompt_tokens"] == 0
    assert summary["total"]["cost_usd"] == 0.0
    
    # Log some usage
    engine.log_usage("test-model", 1000, 2000)
    
    summary2 = engine.get_summary()
    assert summary2["total"]["prompt_tokens"] == 1000
    assert summary2["total"]["completion_tokens"] == 2000
    assert summary2["today"]["prompt_tokens"] == 1000
    assert summary2["today"]["cost_usd"] > 0
