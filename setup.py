"""
Setup script for IPO GMP Scraper
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="ipo-gmp-scraper",
    version="1.0.0",
    author="IPO GMP Scraper Team",
    author_email="your.email@example.com",
    description="A robust scraper for IPO Grey Market Premium data with Telegram notifications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ipo-gmp-scraper",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ipo-scraper=ipo_gmp_scraper:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
