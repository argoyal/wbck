import os
from setuptools import setup, find_packages

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()


def get_version():
    if not os.path.exists("VERSION"):
        raise FileNotFoundError("Version file does not exist")
    
    with open("VERSION", "r") as f:
        version = f.read()

    return version


setup(
    name='wbck',
    version=get_version(),
    author="Arpit Goyal",
    author_email="arpitgoyal.iitkgp@outlook.com",
    description="a command line utility to perform workspace backup",
    long_description_content_type="text/markdown",
    long_description=long_description,
    url="https://github.com/argoyal/wbck.git",
    packages=find_packages(),
    install_requires=[
        'boto3'
    ],
    entry_points={
        'console_scripts': [
            'wbck = wbck:cli',
        ]
    },
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License"
    ]
)
