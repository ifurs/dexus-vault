import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dexus_vault",
    version="0.0.1",
    author="ifurs",
    author_email="ivan.fursovych@gmail.com",
    description="Sync Dex clients with Vault secrets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ifurs/dexus_vault",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
