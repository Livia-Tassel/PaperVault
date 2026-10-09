"""Bounded Windows probe: spawn while a background thread reads piped stdin."""
import faulthandler
import json
import multiprocessing
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path


def child(events):
    events.put({"pid": os.getpid(), "child": "started"})


def inner(mode):
    faulthandler.dump_traceback_later(10, repeat=False)
    sys.stdin.readline()
    if mode == "text":
        threading.Thread(target=lambda: list(sys.stdin), daemon=True).start()
    elif mode == "raw":
        threading.Thread(target=lambda: os.read(0, 1024), daemon=True).start()

    def spawn():
        ctx = multiprocessing.get_context("spawn")
        events = ctx.Queue()
        worker = ctx.Process(target=child, args=(events,))
        worker.start()
        try:
            result = events.get(timeout=12)
            print(json.dumps({"mode": mode, "result": result}), flush=True)
        except queue.Empty:
            print(json.dumps({"mode": mode, "error": "timeout", "pid": worker.pid}), flush=True)
        finally:
            worker.join(timeout=1)
            if worker.is_alive():
                worker.terminate()
                worker.join()
            events.close()
            worker.close()
            faulthandler.cancel_dump_traceback_later()

    thread = threading.Thread(target=spawn)
    thread.start()
    thread.join()


def main():
    for mode in ("none", "text", "raw"):
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--inner", mode],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW)
        messages = queue.Queue()
        threading.Thread(target=lambda: messages.put(proc.stdout.readline()), daemon=True).start()
        proc.stdin.write("bootstrap\n")
        proc.stdin.flush()
        try:
            print(messages.get(timeout=18).strip(), flush=True)
        except queue.Empty:
            print(json.dumps({"mode": mode, "outer": "timeout"}), flush=True)
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        error = proc.stderr.read()
        if error:
            print(error, flush=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--inner" in sys.argv:
        inner(sys.argv[-1])
    else:
        main()
