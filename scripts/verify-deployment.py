#!/usr/bin/env python3
"""Verify selected committed application files in the image and served assets.

Reads source files only; no application imports, configuration or runtime data.
"""
from pathlib import PurePosixPath
import hashlib
import json
import ssl
import subprocess
import sys
import urllib.request


def expected_files(paths):
    result = {}
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Expected repository-relative source paths")
        if path.parts[0] not in {"app", "web"} or path.suffix not in {".py", ".js", ".html", ".css"}:
            continue
        present = subprocess.run(["git", "cat-file", "-e", f"HEAD:{name}"], capture_output=True)
        if present.returncode:  # Tracked deletion: no source expected in image.
            result[name] = None
            continue
        body = subprocess.check_output(["git", "show", f"HEAD:{name}"])
        result[name] = hashlib.sha256(body).hexdigest()
    return result


def verify(paths):
    expected = expected_files(paths)
    program = '''import hashlib,json,pathlib,sys
expected=json.load(sys.stdin)
for name,digest in expected.items():
    path=pathlib.Path("/app")/name
    if digest is None:
        assert not path.exists(), "Deleted source still deployed: "+name
    else:
        assert path.is_file(), "Deployed source absent: "+name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest, "Deployed source differs from commit: "+name
print("Container source verification passed")
'''
    subprocess.run(["docker", "compose", "exec", "-T", "portfolio-analyzer", "python", "-c", program],
                   input=json.dumps(expected), text=True, check=True)
    # Same established self-signed localhost release target as the health gate.
    # No credentials/cookies are sent, and redirects cannot change destination.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    count = 0
    for name, digest in expected.items():
        if not name.startswith("web/") or digest is None:
            continue
        asset = name.removeprefix("web/")
        url = "https://localhost:6443/" + ("" if asset == "index.html" else asset)
        with opener.open(url, timeout=15) as response:
            actual = hashlib.sha256(response.read()).hexdigest()
        if actual != digest:
            raise ValueError(f"Served asset differs from commit: {name}")
        count += 1
    print(f"Verified {len(expected)} container sources and {count} served assets against HEAD")


if __name__ == "__main__":
    verify(sys.argv[1:])
