import os
from codecs import open

from setuptools import setup, find_packages

package_name = "dexus_vault"
here = os.path.abspath(os.path.dirname(__file__))

# Read README.md for docs
with open("README.md", "r", "utf-8") as f:
    long_description = f.read()

# Read __version__.py for version
about = {}
with open(os.path.join(here, package_name, "__version__.py"), "r", "utf-8") as f:
    exec(f.read(), about)

setup(
    name=about["__title__"],
    version=about["__version__"],
    author="ifurs",
    description=about["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=about["__url__"],
    license=about["__license__"],
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
        "hvac~=2.1.0",
        "prometheus_client~=0.20.0",
    ],
    python_requires=">=3.8",
    project_urls={"Source": about["__url__"]},
    entry_points={
        "console_scripts": [f"{about['__title__']} = dexus_vault.__main__:main"]
    },
)
