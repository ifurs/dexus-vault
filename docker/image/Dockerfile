# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ARG VERSION
ARG BUILD_DATE
ARG VCS_REF

# Create a dexus user and switch to it
RUN useradd --create-home dexus
USER dexus

# Install dexus-vault
RUN pip install --no-cache-dir dexus-vault==$VERSION

# Set metadata for the image
LABEL maintainer="ifurs" \
    org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.name="dexus-vault" \
    org.label-schema.description="Synchronizer of Dex clients with secrets in Vault" \
    org.label-schema.version=$VERSION \
    org.label-schema.url="https://github.com/ifurs/dexus-vault/docker/image/" \
    org.label-schema.license="Apache-2.0" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url="https://github.com/ifurs/dexus-vault/" \
    org.label-schema.vcs-type="Git" \
    org.label-schema.vendor="ifurs" \
    org.label-schema.schema-version="1.0"

# Define the command to run when the container starts
ENTRYPOINT ["dexus-vault"]
