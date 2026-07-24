import pytest
import httpx
from unittest.mock import patch, MagicMock
from nimcode.updater import AutoUpdater
import nimcode.updater

@pytest.mark.asyncio
async def test_updater_no_update():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"info": {"version": "0.1.0"}}
        mock_get.return_value = mock_resp
        
        # Test when remote is older than local (which is 0.2.0)
        with patch("nimcode.updater.CURRENT_VERSION", "0.2.0"):
            result = await AutoUpdater.check_for_update()
            assert result is None

@pytest.mark.asyncio
async def test_updater_has_update():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"info": {"version": "9.9.9"}}
        mock_get.return_value = mock_resp
        
        with patch("nimcode.updater.CURRENT_VERSION", "0.2.0"):
            result = await AutoUpdater.check_for_update()
            assert result == "9.9.9"

@pytest.mark.asyncio
async def test_updater_http_error():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Network Error")
        result = await AutoUpdater.check_for_update()
        assert result is None

def test_version_tuple():
    assert AutoUpdater._version_tuple("1.2.3") == (1, 2, 3)
    assert AutoUpdater._version_tuple("invalid") == (0, 0, 0)
