from setuptools import setup, find_packages

setup(
    name="nimcode",
    version="0.3.4",
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
)
