"""
The stack: a disposable mongod, a static image server for the corpus, the backend (through
`app_entry`), and the Vite frontend. Started as one unit, torn down as one unit, and every process
writes its log into the run directory so a failed run can be read afterwards.

DISPOSABLE MEANS A SERVER, NOT A NAMESPACE. `backend/database.py` hard-codes the database name
(`visualDictionaryDB`) and reads the URI from `MONGO_DETAILS`, so there is no namespace a harness
could choose; isolation is a mongod of its own on an ephemeral port with a temp dbpath, which is
stronger anyway — nothing the run does can reach a database that outlives it. Cleanup is the
dbpath being deleted; `--keep` preserves it, and a failed run preserves it regardless and prints
the port/dbpath needed to reopen it.

ONE COUPLING WORTH KNOWING: `database.py` forces `tls=True` on any non-SRV URI unless `PORT` is
set (its proxy for "running on Render"). A plain local mongod refuses TLS, so the backend is
started with `PORT` in its environment. That is a finding, not a fix — it is recorded in the
run's notes.
"""
from __future__ import annotations

import http.server
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PYTHON = sys.executable


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float, *, proc: Optional[subprocess.Popen] = None,
              headers: Optional[Dict[str, str]] = None) -> float:
    """Poll until `url` answers; return the seconds it took. Raises if the process died."""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"process exited with {proc.returncode} before {url} answered")
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status < 500:
                    return time.time() - t0
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(0.25)
    raise TimeoutError(f"{url} did not answer within {timeout}s (last: {last})")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


@dataclass
class Stack:
    run_dir: Path
    keep: bool = False
    fakes: str = "all"
    frontend_mode: str = "dev"            # dev | preview | none
    api_key: str = field(default_factory=lambda: secrets.token_hex(12))
    mongo_port: int = 0
    image_port: int = 0
    backend_port: int = 0
    frontend_port: int = 0
    dbpath: Optional[Path] = None
    procs: Dict[str, subprocess.Popen] = field(default_factory=dict)
    logs: Dict[str, Path] = field(default_factory=dict)
    boot_seconds: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    _image_server: Optional[http.server.ThreadingHTTPServer] = None
    backend_restarts: int = 0

    external_mongo: Optional[str] = None

    # ── urls ──
    @property
    def mongo_uri(self) -> str:
        return self.external_mongo or f"mongodb://127.0.0.1:{self.mongo_port}/vertical-rehearsal"

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.backend_port}"

    @property
    def image_url(self) -> str:
        return f"http://127.0.0.1:{self.image_port}"

    @property
    def app_url(self) -> str:
        return f"http://127.0.0.1:{self.frontend_port}"

    # ── lifecycle ──
    def start(self, images_dir: Path) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._start_mongod()
        self._start_image_server(images_dir)
        self._start_backend()
        if self.frontend_mode != "none":
            self._start_frontend()

    def _log(self, name: str):
        p = self.run_dir / "logs" / f"{name}.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        self.logs[name] = p
        return open(p, "ab")

    def _start_mongod(self) -> None:
        external = os.environ.get("SEMANT_VERTICAL_MONGO_URI")
        if external:
            # CI: a throwaway service container. The app hard-codes its database name, so the
            # namespace is dropped at start and at cleanup; the run record says which server.
            self.external_mongo = external
            from pymongo import MongoClient
            MongoClient(external, serverSelectionTimeoutMS=5000).drop_database("visualDictionaryDB")
            self.mongo_port = int(external.rsplit(":", 1)[-1].split("/")[0]) if ":" in external.rsplit("@", 1)[-1] else 27017
            self.notes.append(f"database: external throwaway server from SEMANT_VERTICAL_MONGO_URI "
                              f"(visualDictionaryDB dropped before and after the run)")
            self.boot_seconds["mongod"] = 0.0
            return
        if shutil.which("mongod") is None:
            raise RuntimeError("mongod is not on PATH; the disposable database cannot be started "
                               "(or set SEMANT_VERTICAL_MONGO_URI to a throwaway server)")
        self.mongo_port = free_port()
        self.dbpath = Path(tempfile.mkdtemp(prefix="vertical-rehearsal-mongo-"))
        t0 = time.time()
        self.procs["mongod"] = subprocess.Popen(
            ["mongod", "--port", str(self.mongo_port), "--dbpath", str(self.dbpath),
             "--bind_ip", "127.0.0.1", "--nojournal"] if _mongod_supports_nojournal() else
            ["mongod", "--port", str(self.mongo_port), "--dbpath", str(self.dbpath),
             "--bind_ip", "127.0.0.1"],
            stdout=self._log("mongod"), stderr=subprocess.STDOUT)
        from pymongo import MongoClient
        deadline = time.time() + 30
        while True:
            try:
                MongoClient(self.mongo_uri, serverSelectionTimeoutMS=500).admin.command("ping")
                break
            except Exception:  # noqa: BLE001
                if self.procs["mongod"].poll() is not None or time.time() > deadline:
                    raise RuntimeError(f"mongod did not come up (log: {self.logs['mongod']})")
                time.sleep(0.2)
        self.boot_seconds["mongod"] = round(time.time() - t0, 2)

    def _start_image_server(self, images_dir: Path) -> None:
        self.image_port = free_port()
        handler = lambda *a, **k: _QuietHandler(*a, directory=str(images_dir), **k)  # noqa: E731
        self._image_server = http.server.ThreadingHTTPServer(("127.0.0.1", self.image_port), handler)
        threading.Thread(target=self._image_server.serve_forever, daemon=True).start()

    def backend_env(self) -> Dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("MONGO_", "CLOUDINARY_", "API_KEY", "PORT"))}
        env.update({
            "SEMANT_VERTICAL_HARNESS": "1",
            "SEMANT_VERTICAL_FAKES": self.fakes,
            "MONGO_DETAILS": self.mongo_uri,
            "PORT": str(self.backend_port),          # see module docstring: disables forced TLS
            "CLOUDINARY_NAME": "vertical-rehearsal",
            "CLOUDINARY_API_KEY": "unset",
            "CLOUDINARY_API_SECRET": "unset",
            "API_KEY": self.api_key,
            "PYTHONPATH": str(ROOT),
            "PYTHONUNBUFFERED": "1",
        })
        # Offline: no model credential may reach the process. `OPENROUTER_API_KEY` is required
        # non-empty at import, so it gets the same nonsense CI uses.
        if self.fakes == "all":
            env["OPENROUTER_API_KEY"] = "ci"
            env.pop("GROQ_API_KEY", None)
        else:
            env.setdefault("OPENROUTER_API_KEY", "ci")
        return env

    def _start_backend(self) -> None:
        if not self.backend_port:
            self.backend_port = free_port()
        t0 = time.time()
        self.procs["backend"] = subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "scripts.vertical_rehearsal_support.app_entry:app",
             "--host", "127.0.0.1", "--port", str(self.backend_port), "--log-level", "warning"],
            cwd=str(ROOT), env=self.backend_env(),
            stdout=self._log("backend"), stderr=subprocess.STDOUT)
        self.boot_seconds["backend"] = round(
            wait_http(f"{self.api_url}/health", 90, proc=self.procs["backend"]), 2)
        if "`PORT` set to disable forced TLS" not in " ".join(self.notes):
            self.notes.append("backend started with `PORT` set to disable forced TLS on the "
                              "local mongod URI (backend/database.py couples TLS to a Render env var)")

    def restart_backend(self, wait_exit: float = 10.0) -> float:
        """Kill (or wait for) the backend and bring it back on the same port. Returns the
        seconds the restart took."""
        proc = self.procs.get("backend")
        t0 = time.time()
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=wait_exit)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        self._start_backend()
        self.backend_restarts += 1
        return round(time.time() - t0, 2)

    def backend_alive(self) -> bool:
        p = self.procs.get("backend")
        return p is not None and p.poll() is None

    def _start_frontend(self) -> None:
        self.frontend_port = free_port()
        env = dict(os.environ)
        env.update({"VITE_API_URL": self.api_url, "VITE_API_KEY": self.api_key,
                    "BROWSER": "none", "NO_COLOR": "1"})
        t0 = time.time()
        if self.frontend_mode == "preview":
            # The gate's Vite build, into a run-private outDir so the repo's `frontend/dist` is
            # never touched. `VITE_API_URL`/`VITE_API_KEY` are baked in at build time.
            out_dir = self.run_dir / "dist"
            tb = time.time()
            subprocess.run(["npx", "vite", "build", "--logLevel", "error", "--outDir", str(out_dir),
                            "--emptyOutDir"], cwd=str(FRONTEND),
                           env=env, check=True, stdout=self._log("vite-build"),
                           stderr=subprocess.STDOUT)
            self.boot_seconds["vite_build"] = round(time.time() - tb, 2)
            self.notes.append(f"frontend served from a production Vite build ({self.boot_seconds['vite_build']}s)")
            cmd = ["npx", "vite", "preview", "--host", "127.0.0.1", "--port",
                   str(self.frontend_port), "--strictPort", "--outDir", str(out_dir)]
        else:
            cmd = ["npx", "vite", "--host", "127.0.0.1", "--port", str(self.frontend_port),
                   "--strictPort", "--clearScreen", "false"]
        self.procs["frontend"] = subprocess.Popen(cmd, cwd=str(FRONTEND), env=env,
                                                  stdout=self._log("frontend"),
                                                  stderr=subprocess.STDOUT)
        self.boot_seconds["frontend"] = round(
            wait_http(f"{self.app_url}/", 120, proc=self.procs["frontend"]), 2)

    def stop(self, *, failed: bool = False) -> Dict[str, str]:
        """Tear everything down. The dbpath is deleted unless `keep` or the run failed — a failed
        run must stay inspectable. Returns what was preserved."""
        preserved: Dict[str, str] = {}
        for name in ("frontend", "backend"):
            p = self.procs.pop(name, None)
            if p is not None and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
        if self._image_server is not None:
            self._image_server.shutdown()
        if self.external_mongo:
            if not (self.keep or failed):
                from pymongo import MongoClient
                try:
                    MongoClient(self.external_mongo, serverSelectionTimeoutMS=5000).drop_database("visualDictionaryDB")
                except Exception:  # noqa: BLE001
                    preserved["external_mongo"] = self.external_mongo
            else:
                preserved["external_mongo"] = f"{self.external_mongo} (visualDictionaryDB kept)"
            return preserved
        if self.keep or failed:
            # Keep mongod running? No — a stray daemon is worse than a reopenable dbpath.
            preserved["mongod_dbpath"] = str(self.dbpath)
            preserved["reopen"] = f"mongod --dbpath {self.dbpath} --port {self.mongo_port}"
        p = self.procs.pop("mongod", None)
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
        if not (self.keep or failed) and self.dbpath is not None:
            shutil.rmtree(self.dbpath, ignore_errors=True)
        return preserved


def _mongod_supports_nojournal() -> bool:
    # `--nojournal` was removed in 6.0; every modern mongod refuses it. Detect once.
    try:
        out = subprocess.run(["mongod", "--version"], capture_output=True, text=True, timeout=10).stdout
        major = int(out.split("db version v", 1)[1].split(".", 1)[0])
        return major < 6
    except Exception:  # noqa: BLE001
        return False
