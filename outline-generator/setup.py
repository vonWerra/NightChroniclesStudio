#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Setup script for YouTube Series Outline Generator."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme = Path("README.md")
long_description = readme.read_text(encoding="utf-8") if readme.exists() else ""

setup(
    name="outline-generator",
    version="2.0.0",
    description="YouTube Series Outline Generator with AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/outline-generator",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "aiohttp>=3.9.0",
        "aiofiles>=23.2.1",
        "backoff>=2.2.1",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "structlog>=24.1.0",
        "openai>=1.6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.12.0",
            "isort>=5.13.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
        ],
        "enhanced": [
            "colorama>=0.4.6",
            "rich>=13.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "outline-generator=generate_outline:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="youtube, outline, generator, ai, gpt, openai",
)
