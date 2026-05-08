"""
Setup configuration for the decentralized voting system.
"""

from __future__ import annotations

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="decentralized-voting-system",
    version="1.0.0",
    author="Mani",
    description=(
        "A Python-based decentralized voting system with cryptographic "
        "signatures, vote chain, ZKP, and consensus validation"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/decentralized-voting-system",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security :: Cryptography",
    ],
    python_requires=">=3.10",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
            "flake8>=6.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "dvs-cli=src.cli:main",
        ],
    },
)
