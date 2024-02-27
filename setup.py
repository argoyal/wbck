from setuptools import setup, find_packages

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setup(
    name='wbck',
    version='1.0.2',
    author="Arpit Goyal",
    author_email="arpitgoyal.iitkgp@outlook.com",
    description="a command line utility to perform workspace backup",
    long_description_content_type="text/markdown",
    long_description=long_description,
    url="https://github.com/argoyal/workspace-backup.git",
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
