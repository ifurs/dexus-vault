# Build from the repository root:
#   docker build -f docker/image/Dockerfile .
# Base images are pinned by digest (multi-arch index); Dependabot updates them.
ARG PYTHON_IMAGE=python:3.13-slim@sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f

FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app
WORKDIR /src
# dependencies first, so they stay cached while only the code changes
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --extra aws --no-install-project
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY dexus_vault ./dexus_vault
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra aws --no-editable

FROM ${PYTHON_IMAGE}
# pip is not needed at runtime and vendors its own (often outdated) certifi,
# urllib3 and msgpack, which image scanners rightly report
RUN python -m pip uninstall --yes --quiet pip \
    && rm -rf /usr/local/lib/python3.*/ensurepip
COPY --from=build /app /app
ENV PATH="/app/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# unprivileged user, the image needs no write access
USER 65532:65532
EXPOSE 8000
ENTRYPOINT ["dexus-vault"]
