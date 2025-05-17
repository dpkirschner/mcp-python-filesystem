from setuptools import setup, find_packages

setup(
    name="mcp-python-filesystem",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        # Add your project's dependencies here
        "pydantic>=1.8.0",
        "fastapi",
        "aiofiles",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0",
            "pytest-cov>=3.0.0",
            "pytest-mock>=3.10.0",
            "black",
            "isort",
            "mypy",
            "flake8",
        ],
    },
)
