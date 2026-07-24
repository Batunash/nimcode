import os
import sys
import json
import httpx
import asyncio
import re

NIM_API_KEY = os.environ.get("NIM_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODELS_FILE = "models.json"

def bump_setup_version(new_version):
    with open("setup.py", "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'version="[0-9\.]+"', f'version="{new_version}"', content)
    with open("setup.py", "w", encoding="utf-8") as f:
        f.write(content)

def bump_package_json(new_version):
    pkg_path = os.path.join("vscode-extension", "package.json")
    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    pkg["version"] = new_version
    with open(pkg_path, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2)

def get_current_version():
    with open("setup.py", "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'version="([0-9\.]+)"', content)
    return match.group(1) if match else "0.0.1"

def increment_patch(version: str):
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)

async def check_and_update_models():
    if not NIM_API_KEY:
        print("NIM_API_KEY is required.")
        sys.exit(1)

    print("Fetching models from NVIDIA NIM...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {NIM_API_KEY}"})
        if response.status_code != 200:
            print(f"Failed to fetch models: {response.text}")
            sys.exit(1)
            
        data = response.json()
        current_models = sorted([m["id"] for m in data.get("data", [])])

    old_models = []
    if os.path.exists(MODELS_FILE):
        with open(MODELS_FILE, "r", encoding="utf-8") as f:
            old_models = sorted(json.load(f))

    if current_models == old_models:
        print("No changes in models.")
        print("NO_CHANGES") # Signal to bash script/Github Action
        return

    print("Models have changed. Updating models.json...")
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_models, f, indent=2)

    added = set(current_models) - set(old_models)
    removed = set(old_models) - set(current_models)

    print(f"Added: {added}")
    print(f"Removed: {removed}")

    current_version = get_current_version()
    new_version = increment_patch(current_version)
    
    print(f"Bumping version from {current_version} to {new_version}")
    bump_setup_version(new_version)
    bump_package_json(new_version)
    
    # Save a changelog msg
    msg = f"chore(models): Auto-update NIM models to v{new_version}\n\n"
    if added:
        msg += f"Added:\n" + "\n".join([f"- {m}" for m in added]) + "\n"
    if removed:
        msg += f"Removed:\n" + "\n".join([f"- {m}" for m in removed]) + "\n"
        
    with open("changelog.txt", "w", encoding="utf-8") as f:
        f.write(msg)
        
    print("UPDATE_SUCCESS")

if __name__ == "__main__":
    asyncio.run(check_and_update_models())
