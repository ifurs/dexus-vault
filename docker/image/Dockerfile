# Build from the repository root:
#   docker build -f docker/image/Dockerfile .
ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS build
WORKDIR /src
COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY dexus_vault ./dexus_vault
RUN pip wheel --no-cache-dir --wheel-dir /wheels --constraint requirements.txt ".[aws]"

FROM python:${PYTHON_VERSION}-slim
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index /wheels/*.whl

# unprivileged user, the image needs no write access
USER 65532:65532
EXPOSE 8000
ENTRYPOINT ["dexus-vault"]
