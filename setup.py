#!/usr/bin/env python3
"""
setup.py for cli-anything-issuebadge

Install with: pip install -e .
Or publish to PyPI: python -m build && twine upload dist/*
"""

from setuptools import setup, find_namespace_packages

with open("cli_anything/issuebadge/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-issuebadge",
    version="1.0.0",
    author="IssueBadge",
    author_email="product@issuebadge.com",
    description="CLI harness for IssueBadge — issue, manage and verify digital certificates and badges via the IssueBadge API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/issuebadge2026/cli-anything-issuebadge",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-issuebadge=cli_anything.issuebadge.issuebadge_cli:main",
        ],
    },
    package_data={
        "cli_anything.issuebadge": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,
)
