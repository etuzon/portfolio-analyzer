#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 \"commit message\" <file> [file ...]" >&2
}

if (( $# < 2 )); then
  usage
  exit 2
fi

message=$1
shift
files=("$@")

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$script_dir/.." && pwd)
cd "$repo_dir"

if [[ -z "$message" ]]; then
  echo "Commit message cannot be empty." >&2
  exit 2
fi

if ! git diff --cached --quiet; then
  echo "Refusing to continue because the Git index already contains staged changes." >&2
  exit 1
fi

for file in "${files[@]}"; do
  if [[ "$file" = /* || "$file" == ".." || "$file" == ../* || "$file" == */../* || "$file" == */.. ]]; then
    echo "Use a repository-relative file path without '..': $file" >&2
    exit 2
  fi
  if [[ -d "$file" ]]; then
    echo "List files explicitly; directory paths are not accepted: $file" >&2
    exit 2
  fi
  if [[ ! -e "$file" ]] && git diff --quiet -- "$file"; then
    echo "File does not exist and is not a tracked deletion: $file" >&2
    exit 2
  fi
done

echo "Checking selected files..."
git diff --check -- "${files[@]}"
bash -n "$0"

echo "Running tests..."
./.venv/bin/python -m pytest

echo "Committing selected files..."
git add -- "${files[@]}"
if git diff --cached --quiet; then
  echo "No selected changes to commit." >&2
  exit 1
fi
git commit -m "$message" -- "${files[@]}"

echo "Building and deploying Docker Compose services..."
docker compose up --build -d

health_url=https://localhost:6443/api/health
health_response=""
for attempt in {1..30}; do
  if health_response=$(curl --insecure --fail --silent --show-error "$health_url" 2>/dev/null); then
    if [[ "$health_response" == *'"status":"ok"'* ]]; then
      break
    fi
  fi
  if (( attempt == 30 )); then
    echo "Deployment health check failed: $health_url" >&2
    docker compose ps
    exit 1
  fi
  sleep 1
done

docker compose ps
echo "Committed $(git rev-parse --short HEAD) and deployed successfully."
echo "Health: $health_response"
