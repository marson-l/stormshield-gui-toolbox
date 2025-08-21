from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="stormshield-gui-toolbox",
    version="2.0.0",
    author="marson-l",
    author_email="lanzo.marson@protonmail.com",
    description="A modern GUI Toolbox for Stormshield SNS appliances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/marson-l/stormshield-gui-toolbox",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "Environment :: X11 Applications :: Qt",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "stormshield-gui=src.main_gui:main"
        ],
    },
    keywords="stormshield, sns, firewall, gui, network, administration",
    project_urls={
        "Bug Reports": "https://github.com/marson-l/stormshield-gui-toolbox/issues",
        "Source": "https://github.com/marson-l/stormshield-gui-toolbox",
        "Documentation": "https://github.com/marson-l/stormshield-gui-toolbox/blob/main/README.md",
    },
)
