from setuptools import setup, find_packages
import os
from pathlib import Path

# Single source of truth for version
version = {}
with open(os.path.join("src", "nimcode", "__version__.py")) as f:
    exec(f.read(), version)

setup(
    name="nimcode",
    version=version["__version__"],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "httpx>=0.27.0",
        "rich>=13.7.0",
        "prompt_toolkit>=3.0.0",
        "mcp>=1.2.0",
        "watchdog>=3.0.0"
    ],
    entry_points={
        "console_scripts": [
            "nimcode=nimcode.cli:main",
        ],
    },
    author="Autonomous Agent",
    description="A standalone, robust coding agent for NVIDIA NIM models.",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/Batunash/nimcode",
    python_requires=">=3.8",
)
