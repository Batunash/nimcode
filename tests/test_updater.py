import pytest
import httpx
import respx
from nimcode.updater import AutoUpdater, CURRENT_VERSION

@pytest.mark.asyncio
@respx.mock
async def test_auto_updater_no_update():
    # Mock PyPI response to return current version
    respx.get("https://pypi.org/pypi/nimcode/json").respond(
        status_code=200,
        json={"info": {"version": CURRENT_VERSION}}
    )
    
    result = await AutoUpdater.check_for_update()
    assert result is None

@pytest.mark.asyncio
@respx.mock
async def test_auto_updater_update_available():
    # Mock PyPI response to return higher version
    respx.get("https://pypi.org/pypi/nimcode/json").respond(
        status_code=200,
        json={"info": {"version": "9.9.9"}}
    )
    
    result = await AutoUpdater.check_for_update()
    assert result == "9.9.9"

@pytest.mark.asyncio
@respx.mock
async def test_auto_updater_network_error():
    # Mock PyPI response to fail
    respx.get("https://pypi.org/pypi/nimcode/json").respond(
        status_code=500
    )
    
    result = await AutoUpdater.check_for_update()
    assert result is None
