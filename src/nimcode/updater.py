import httpx
import logging

logger = logging.getLogger(__name__)

CURRENT_VERSION = "3.0.0"

class AutoUpdater:
    @staticmethod
    async def check_for_update() -> str:
        """
        Check PyPI for the latest nimcode version.
        Returns the latest version string if > CURRENT_VERSION, else None.
        """
        try:
            from .config import load_settings
            settings = load_settings()
            t_upd = settings.get("timeout_updater", 3.0)
            t_upd = None if t_upd == 0 else t_upd
            
            async with httpx.AsyncClient(timeout=t_upd) as client:
                response = await client.get("https://pypi.org/pypi/nimcode/json")
                if response.status_code == 200:
                    data = response.json()
                    latest = data["info"]["version"]
                    
                    # Simple version comparison
                    if AutoUpdater._version_tuple(latest) > AutoUpdater._version_tuple(CURRENT_VERSION):
                        return latest
        except Exception as e:
            logger.debug(f"Failed to check for updates: {e}")
        return None

    @staticmethod
    def _version_tuple(v: str) -> tuple:
        try:
            return tuple(map(int, (v.split("."))))
        except:
            return (0, 0, 0)
