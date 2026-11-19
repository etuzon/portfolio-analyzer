#!/usr/bin/env bash
# Installed as ~/.local/bin/codex; delegate all ordinary CLI operations unchanged.
set -u

launcher_path=$(readlink -f -- "${BASH_SOURCE[0]}")
repository_root=$(cd -- "$(dirname -- "$launcher_path")/.." && pwd -P)
current_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
real_codex=/usr/local/bin/codex

# Recognize prompt-free startup flags without intercepting subcommands/prompts.
show_backlog=true
inline_args=(--no-alt-screen)
for argument in "$@"; do
    case "$argument" in
        --no-alt-screen) inline_args=() ;;
        --yolo|--dangerously-bypass-approvals-and-sandbox) ;;
        *) show_backlog=false ;;
    esac
done

if [[ -t 0 && -t 1 && "$current_root" == "$repository_root" && "$show_backlog" == true ]]; then
    if python3 "$repository_root/scripts/show-codex-backlog.py"; then
        export PORTFOLIO_CODEX_BACKLOG_SHOWN=1
    fi
    # Keep the tables visible above the CLI and available in terminal scrollback.
    exec "$real_codex" "${inline_args[@]}" "$@"
fi

exec "$real_codex" "$@"
