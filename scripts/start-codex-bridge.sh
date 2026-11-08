#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bridge_dir=$(cd "$repo_dir" && "$repo_dir/.venv/bin/python" - "$repo_dir" <<'PY'
from pathlib import Path
import sys
from app.codex_bridge import bridge_runtime_directory
print(bridge_runtime_directory(Path(sys.argv[1])))
PY
)
bridge_socket=$bridge_dir/bridge.sock
bridge_pid=$bridge_dir/bridge.pid
restart=false
use_service=true
for option in "$@"; do
  case "$option" in
    --restart) restart=true ;;
    --no-service) use_service=false ;;
    *) echo "Usage: $0 [--restart] [--no-service]" >&2; exit 2 ;;
  esac
done

local_provider=$(cd "$repo_dir" && "$repo_dir/.venv/bin/python" -c 'from app.config import load_config; from app.llm_assistant import assistant_settings; print(assistant_settings(load_config().raw)["provider"])')
if [[ "$local_provider" == "local_claude" ]]; then
  command -v claude >/dev/null || { echo "Install Claude Code and sign in first." >&2; exit 1; }
  claude auth status >/dev/null 2>&1 || { echo "Sign in to Claude Code first." >&2; exit 1; }
else
  command -v codex >/dev/null || { echo "Install Codex CLI and sign in with codex login first." >&2; exit 1; }
  codex login status >/dev/null 2>&1 || { echo "Sign in with codex login first." >&2; exit 1; }
fi
command -v setsid >/dev/null || { echo "The local bridge requires the Linux setsid utility." >&2; exit 1; }
mkdir -p -- "$bridge_dir"
chmod 700 "$bridge_dir"
service_available=false
if $use_service && command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
  service_available=true
  bridge_unit=$("$repo_dir/.venv/bin/python" - "$repo_dir" "$bridge_socket" <<'PY'
import hashlib, sys
print("portfolio-codex-bridge-" + hashlib.sha256((sys.argv[1] + "\0" + sys.argv[2]).encode()).hexdigest()[:12] + ".service")
PY
)
  if $restart && systemctl --user is-active --quiet "$bridge_unit"; then
    systemctl --user stop "$bridge_unit"
  fi
  # Migrate the earlier repo-only unit only when it owns this exact socket.
  # Another socket instance may be serving separate live requests.
  if $restart; then
    legacy_unit=$("$repo_dir/.venv/bin/python" - "$repo_dir" "$bridge_socket" <<'PY'
import hashlib, subprocess, sys
from app.codex_bridge import process_owns_bridge_socket
unit = "portfolio-codex-bridge-" + hashlib.sha256(sys.argv[1].encode()).hexdigest()[:12] + ".service"
result = subprocess.run(["systemctl", "--user", "show", unit, "--property=MainPID", "--value"], capture_output=True, text=True)
try:
    pid = int(result.stdout.strip())
except ValueError:
    pid = 0
if process_owns_bridge_socket(pid, sys.argv[2]):
    print(unit)
PY
)
    if [[ -n "$legacy_unit" ]]; then
      systemctl --user stop "$legacy_unit"
      systemctl --user disable "$legacy_unit" >/dev/null 2>&1
    fi
  fi
fi
if $restart; then
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
# User services survive the initiating terminal/task, restart after a crash,
# and start at the next user login. Fall back for hosts without a user manager.
if $service_available; then
  bridge_unit=$("$repo_dir/.venv/bin/python" - "$repo_dir" "$bridge_socket" <<'PY'
import hashlib, os, sys
from pathlib import Path
repo, socket_path = Path(sys.argv[1]), sys.argv[2]
unit = "portfolio-codex-bridge-" + hashlib.sha256((str(repo) + "\0" + socket_path).encode()).hexdigest()[:12] + ".service"
def quoted(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
directory = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")/"systemd/user"
directory.mkdir(parents=True, exist_ok=True)
lines = ["[Unit]", "Description=Portfolio Analyzer local AI bridge", "", "[Service]", "Type=simple",
         "WorkingDirectory=" + str(repo).replace('%', '%%'),
         "ExecStart=" + quoted(repo/".venv/bin/python") + " -m app.codex_bridge --socket " + quoted(socket_path),
         "Environment=" + quoted("PATH=" + os.environ["PATH"]),
         "Restart=on-failure", "RestartSec=2", "UMask=0077", "", "[Install]", "WantedBy=default.target"]
if os.environ.get("CODEX_HOME"):
    lines.insert(lines.index("Restart=on-failure"), "Environment=" + quoted("CODEX_HOME="+os.environ["CODEX_HOME"]))
(directory/unit).write_text("\n".join(lines)+"\n")
print(unit)
PY
)
  systemctl --user daemon-reload
  systemctl --user enable "$bridge_unit" >/dev/null 2>&1
  if $restart; then
    systemctl --user restart "$bridge_unit"
  else
    systemctl --user start "$bridge_unit"
  fi
else
  nohup setsid "$repo_dir/.venv/bin/python" -m app.codex_bridge --socket "$bridge_socket" </dev/null >"$bridge_dir/bridge.log" 2>&1 &
  echo "$!" >"$bridge_pid"
fi
for attempt in {1..30}; do
  if [[ -S "$bridge_socket" ]]; then
    echo "Local AI bridge started. Chat uses the configured CLI sign-in; no API key is needed."
    exit 0
  fi
  sleep 0.1
done
echo "Local Codex bridge did not start. Check its private log." >&2
exit 1
