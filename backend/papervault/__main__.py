from __future__ import annotations

import multiprocessing

# PyInstaller's frozen worker dispatch must run before heavyweight imports.
if __name__ == "__main__":
    multiprocessing.freeze_support()

import argparse
import json
import logging
import os
import socket
import sys
import threading
from pathlib import Path


def main():
    import uvicorn
    from papervault.api import create_app
    parser = argparse.ArgumentParser(description="PaperVault local backend")
    parser.add_argument("--dev", action="store_true", help="Standalone development server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if args.dev:
        bootstrap = {"token": os.environ.get("PAPERVAULT_DEV_TOKEN", "dev-token")}
    else:
        line = sys.stdin.readline()
        if not line:
            return
        bootstrap = json.loads(line)
        if not isinstance(bootstrap.get("token"), str) or len(bootstrap["token"]) < 32:
            raise ValueError("Sidecar requires a per-session authentication token")
    config_dir = args.config or Path(bootstrap.get("config_path") or
                                    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PaperVault")
    # Treat config_path as an app-data directory; settings live inside it.
    models = args.models or (Path(bootstrap["models_path"]) if bootstrap.get("models_path") else None)
    library = args.library or (Path(bootstrap["library_path"]) if bootstrap.get("library_path") else None)
    app = create_app(bootstrap["token"], config_dir, library, models)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", args.port if args.dev else 0))
    sock.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", access_log=False, log_level="warning"))
    if not args.dev:
        def control():
            for line in sys.stdin:
                try:
                    if json.loads(line).get("type") == "shutdown":
                        break
                except (ValueError, AttributeError):
                    continue
            server.should_exit = True
        threading.Thread(target=control, name="desktop-control", daemon=True).start()
    print(json.dumps({"type": "ready", "port": sock.getsockname()[1], "protocol": 1}), flush=True)
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()
        app.state.services.close()


if __name__ == "__main__":
    main()
