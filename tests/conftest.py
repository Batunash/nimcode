import pytest
import asyncio

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    async def fast_sleep(*args, **kwargs):
        pass
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
