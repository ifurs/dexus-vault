#!/usr/bin/env bash
# Decide whether the current checkout is a new release.
#
# Prints and, inside GitHub Actions, writes to $GITHUB_OUTPUT:
#   version=<__version__>
#   release=true|false   (true when no tag for this version exists yet)
# Fails when the version is not MAJOR.MINOR.PATCH, or lower than the latest tag.
# Needs the tags in the checkout (actions/checkout with fetch-tags).
set -euo pipefail

cd "$(dirname "$0")/.."

out() {
    echo "$1"
    if [ -n "${GITHUB_OUTPUT:-}" ]; then
        echo "$1" >> "$GITHUB_OUTPUT"
    fi
}

version=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' dexus_vault/__version__.py)
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "::error::__version__ '$version' is not MAJOR.MINOR.PATCH" >&2
    exit 1
fi
out "version=$version"

if git rev-parse -q --verify "refs/tags/$version" > /dev/null; then
    echo "Version $version is already released" >&2
    out "release=false"
    exit 0
fi

latest=$(git tag --list '[0-9]*.[0-9]*.[0-9]*' | sort -V | tail -1)
if [ -n "$latest" ] && [ "$(printf '%s\n%s\n' "$latest" "$version" | sort -V | tail -1)" != "$version" ]; then
    echo "::error::$version is lower than the latest release $latest" >&2
    exit 1
fi
echo "New release $version (latest: ${latest:-none})" >&2
out "release=true"
