#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bridge_dir=${PORTFOLIO_CODEX_DIR:-/tmp/portfolio-codex}
bridge_socket=$bridge_dir/bridge.sock
bridge_pid=$bridge_dir/bridge.pid

command -v codex >/dev/null || { echo "Install Codex CLI and sign in with codex login first." >&2; exit 1; }
command -v setsid >/dev/null || { echo "The local bridge requires the Linux setsid utility." >&2; exit 1; }
codex login status >/dev/null 2>&1 || { echo "Sign in with codex login first." >&2; exit 1; }
mkdir -p -- "$bridge_dir"
chmod 700 "$bridge_dir"
if [[ "${1:-}" == "--restart" ]]; then
  "$repo_dir/.venv/bin/python" - "$bridge_pid" "$bridge_socket" <<'PY'
import os, signal, sys, time
from pathlib import Path
pid_path, socket_path = Path(sys.argv[1]), sys.argv[2]
if pid_path.exists():
    try:
        pid = int(pid_path.read_text().strip())
        if pid <= 1:
            raise ValueError()
        command = Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0")
        if "app.codex_bridge" not in command or socket_path not in command:
            raise SystemExit("Refusing to stop a process that is not this Codex bridge.")
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        pid_path.unlink(missing_ok=True)
    except (FileNotFoundError, ProcessLookupError):
        pid_path.unlink(missing_ok=True)
    except ValueError:
        raise SystemExit("Invalid bridge PID file.")
PY
fi
if "$repo_dir/.venv/bin/python" - "$bridge_socket" <<'PY'
import socket, sys
try:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(1)
        client.connect(sys.argv[1])
except OSError:
    raise SystemExit(1)
PY
then
  echo "Local Codex bridge is already running."
  exit 0
fi
if [[ -f "$bridge_pid" ]] && kill -0 "$(cat -- "$bridge_pid")" 2>/dev/null; then
  echo "A bridge process is still starting; retry shortly." >&2
  exit 1
fi
"$repo_dir/.venv/bin/python" - "$bridge_socket" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
if path.is_socket():
    path.unlink()
elif path.exists():
    raise SystemExit("Refusing to replace a non-socket file.")
PY
cd "$repo_dir"
nohup setsid "$repo_dir/.venv/bin/python" -m app.codex_bridge --socket "$bridge_socket" </dev/null >"$bridge_dir/bridge.log" 2>&1 &
echo "$!" >"$bridge_pid"
for attempt in {1..30}; do
  if [[ -S "$bridge_socket" ]]; then
    echo "Local Codex bridge started. Chat uses the existing Codex sign-in; no API key is needed."
    exit 0
  fi
  sleep 0.1
done
echo "Local Codex bridge did not start. Check its private log." >&2
exit 1
