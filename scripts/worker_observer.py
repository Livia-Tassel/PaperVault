"""Read exit codes of already-owned Windows test workers without changing them."""
from __future__ import annotations

import copy
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import threading
import time


class WorkerObserver:
    def __init__(self):
        self.lock = threading.RLock()
        self.entries = {}
        self.enabled = os.name == "nt"
        if self.enabled:
            api = self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            api.OpenProcess.restype = wintypes.HANDLE
            api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            api.WaitForSingleObject.restype = wintypes.DWORD
            api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            api.GetExitCodeProcess.restype = wintypes.BOOL
            api.CloseHandle.argtypes = [wintypes.HANDLE]
            api.CloseHandle.restype = wintypes.BOOL

    def observe(self, process, command):
        """Caller must identify this process as a child of its own backend."""
        if not self.enabled:
            return
        with self.lock:
            key = (process.pid, process.create_time())
            if key in self.entries:
                return
            source = command[command.index("--source") + 1] if "--source" in command else None
            record = {"pid": process.pid, "created_at_epoch": key[1], "command": command,
                      "source": source, "exit_code": None, "state": "observed"}
            # Acquire while alive; querying a PID only after it disappears loses
            # its exit status and can confuse a newly reused PID with this worker.
            handle = self.api.OpenProcess(0x1000 | 0x100000, False, process.pid)
            if not handle:
                record.update(state="handle_unavailable", winerror=ctypes.get_last_error())
            self.entries[key] = {"handle": handle, "record": record}

    def poll(self):
        if not self.enabled:
            return
        with self.lock:
            for entry in self.entries.values():
                handle, record = entry["handle"], entry["record"]
                if not handle:
                    continue
                state = self.api.WaitForSingleObject(handle, 0)
                if state == 0:
                    code = wintypes.DWORD()
                    if self.api.GetExitCodeProcess(handle, ctypes.byref(code)):
                        record.update(state="exited", exit_code=code.value, exit_code_hex=f"0x{code.value:08X}")
                    else:
                        record.update(state="exit_query_failed", winerror=ctypes.get_last_error())
                    self.api.CloseHandle(handle)
                    entry["handle"] = None
                elif state == 0xFFFFFFFF:
                    record.update(state="wait_failed", winerror=ctypes.get_last_error())

    def snapshot(self, source=None, settle_seconds=0):
        deadline = time.monotonic() + settle_seconds
        while True:
            self.poll()
            with self.lock:
                records = [copy.deepcopy(entry["record"]) for entry in self.entries.values()]
            if source is not None:
                target = os.path.normcase(str(Path(source).resolve()))
                records = [record for record in records if record["source"] and
                           os.path.normcase(str(Path(record["source"]).resolve())) == target]
            if not records or all(record["state"] != "observed" for record in records) or time.monotonic() >= deadline:
                return records
            time.sleep(.05)

    def close(self):
        self.poll()
        with self.lock:
            for entry in self.entries.values():
                if entry["handle"]:
                    entry["record"].update(state="still_running_at_observer_close")
                    self.api.CloseHandle(entry["handle"])
                    entry["handle"] = None
