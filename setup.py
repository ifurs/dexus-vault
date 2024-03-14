import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

# Read README.md for docs
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="dexus_vault",
    version="0.1.0",
    author="ifurs",
    description="Tool for synchronization of Dex clients with secrets managed in HashiCorp's Vault",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ifurs/dexus_vault",
    packages=find_packages(),
    classifiers=(
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Operating System :: OS Independent",
    ),
    install_requires=[
        "grpcio~=1.62.0",
        "grpcio-tools~=1.60.1",
        "googleapis-common-protos>=1.62.0",
        "protobuf~=4.25.3",
        " hvac~=2.1.0",
    ],
    python_requires=">=3.8",
)
