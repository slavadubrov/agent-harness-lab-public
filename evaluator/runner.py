"""Run one candidate episode under an execution profile, speaking ``harness-observation/1``.

The evaluator owns everything outside the candidate process: the database and the tools
(``support.py``), the model and classifier connections (``broker.py``), the supervisor,
the record of events and the verdict. The candidate gets a customer message and the tool
schemas, and can only send requests over stdin and stdout. This module imports no
LangChain, LangGraph or harness code.

Profiles:

- ``docker``: the candidate runs in a container with no network, a read-only root
  filesystem, its own files mounted read-only, a small ``/tmp``, an unprivileged user,
  no capabilities, and CPU, memory and process limits (``DOCKER_FLAGS``). The probes in
  ``evaluator/fixtures.py`` test each restriction.
- ``local``: a subprocess of the same user with an empty environment. That is process
  separation only: the candidate can read and write your files and reach the network.
  It exists for reviewed fixtures, and every result says ``containment: false``.

There is no fallback from ``docker`` to ``local``: a missing image or daemon is an error.
"""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROTOCOL = "harness-observation/1"
IMAGE = "agent-harness-lab-candidate:py312"
MAX_LINE = 2 * 1024 * 1024
MAX_OUTPUT = 16 * 1024 * 1024
MAX_MESSAGES = 300
# Every flag is a restriction the probes check; see the module docstring.
DOCKER_FLAGS = [
    "--network=none",
    "--read-only",
    "--tmpfs=/tmp:rw,nosuid,nodev,size=64m",
    "--user=65534:65534",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--pids-limit=128",
    "--memory=768m",
    "--memory-swap=768m",
    "--cpus=1",
    "--env=HOME=/tmp",
    "--workdir=/candidate",
]
FIELDS = {
    "tool": {"name", "arguments", "call_id"},
    "http": {"method", "url", "headers", "body"},
    "approval": {"request"},
    "finish": {"reply"},
}


class ProtocolError(Exception):
    """The candidate broke the protocol; the episode stops and the message is not served."""


class ProfileUnavailable(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode())


EVALUATOR_SHA256 = digest(
    {p.name: sha256(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))}
)


@dataclass(frozen=True)
class Artifact:
    """The candidate's files, captured once. Episodes run these bytes, never the source tree."""

    files: tuple[tuple[str, bytes], ...]
    entry: str
    label: str
    args: tuple[str, ...] = ()

    @property
    def sha256(self) -> str:
        files = [[path, sha256(data)] for path, data in self.files]
        return digest({"files": files, "entry": self.entry, "args": list(self.args)})

    def write(self, root: Path) -> None:
        for path, data in self.files:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def capture(
    root: Path, patterns: list[str], entry: str, label: str, args: tuple[str, ...] = ()
) -> Artifact:
    """Copy the files matching ``patterns`` under ``root``. Symlinks are refused."""
    paths = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})
    if any(p.is_symlink() for p in paths):
        raise ValueError("a candidate artifact must not contain symlinks")
    files = tuple((p.relative_to(root).as_posix(), p.read_bytes()) for p in paths)
    if entry not in {path for path, _ in files}:
        raise ValueError(f"entry {entry} is not in the artifact")
    return Artifact(files, entry, label, args)


def single_file(source: bytes, label: str) -> Artifact:
    return Artifact((("candidate.py", source),), "candidate.py", label)


def accepts(result: dict[str, Any], artifact: Artifact, task_sha256: str) -> bool:
    """Whether a stored result still describes this exact candidate, task and evaluator.

    A changed file, task or evaluator invalidates an earlier pass. A result is evidence
    only when the evaluator wrote it; never pass a result a candidate supplied."""
    return (
        result.get("verdict", {}).get("obligations") is True
        and result.get("candidate", {}).get("sha256") == artifact.sha256
        and result.get("task", {}).get("sha256") == task_sha256
        and result.get("evaluator_sha256") == EVALUATOR_SHA256
    )


@dataclass
class Recorder:
    """The evaluator's own event log for one episode."""

    run_id: str
    started: float = field(default_factory=time.monotonic)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, kind: str, **data: Any) -> dict[str, Any]:
        event = {
            "seq": len(self.events),
            "t_ms": round((time.monotonic() - self.started) * 1000, 1),
            "source": "evaluator",
            "kind": kind,
            **data,
        }
        self.events.append(event)
        return event


def docker_ready() -> str | None:
    """The image id if the daemon answers and the candidate image exists, else None."""
    if shutil.which("docker") is None:
        return None
    out = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return out.stdout.strip() if out.returncode == 0 else None


def command(profile: str, root: Path, artifact: Artifact, name: str) -> list[str]:
    if profile == "local":
        return [sys.executable, "-I", "-u", str(root / artifact.entry), *artifact.args]
    if profile == "docker":
        mount = f"--volume={root}:/candidate:ro"
        return [
            *["docker", "run", "--rm", "-i", f"--name={name}", *DOCKER_FLAGS, mount, IMAGE],
            *["python", "-I", "-u", f"/candidate/{artifact.entry}", *artifact.args],
        ]
    raise ValueError(f"unknown profile {profile}")


def client_env(profile: str) -> dict[str, str]:
    """The environment of the process the evaluator starts. A local candidate gets none.
    The docker client needs enough to find the daemon; the container gets only --env flags."""
    if profile == "local":
        return {}
    keep = ("PATH", "HOME", "TMPDIR", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")
    return {k: os.environ[k] for k in keep if k in os.environ}


def run_episode(
    artifact: Artifact,
    hello: dict[str, Any],
    handlers: dict[str, Any],
    *,
    profile: str,
    recorder: Recorder,
    timeout_s: float = 120.0,
    trusted: bool = False,
) -> dict[str, Any]:
    """Run the candidate until it finishes, breaks the protocol, crashes or times out.

    ``handlers`` maps a request kind (tool, http, approval) to a function that takes the
    message and returns the response the candidate gets. They record their own events.
    """
    if profile == "local" and not trusted:
        raise ValueError("the local profile is for reviewed fixtures only: pass trusted=True")
    image_id = None
    if profile == "docker":
        image_id = docker_ready()
        if image_id is None:
            raise ProfileUnavailable(
                f"docker profile unavailable: start Docker and build {IMAGE} "
                "(make candidate-image). There is no fallback to the local profile."
            )
    run_id = recorder.run_id
    name = f"episode-{run_id}"
    reply: str | None = None
    error: str | None = None
    termination = "finished"
    exit_code: int | None = None
    stderr_tail = ""
    with tempfile.TemporaryDirectory(prefix="candidate-") as tmp:
        root = Path(tmp) / "candidate"
        root.mkdir()
        artifact.write(root)
        os.chmod(tmp, 0o755)
        for path in [root, *root.rglob("*")]:
            os.chmod(path, 0o755 if path.is_dir() else 0o644)
        cmd = command(profile, root, artifact, name)
        stderr = open(Path(tmp) / "stderr", "w+b")  # noqa: SIM115 - closed in finally
        proc = subprocess.Popen(
            cmd,
            cwd=tmp,
            env=client_env(profile),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        started = time.monotonic()
        buffer = b""
        received = 0
        count = 0

        def send(value: dict[str, Any]) -> None:
            proc.stdin.write(json.dumps(value).encode() + b"\n")
            proc.stdin.flush()

        try:
            send({"protocol": PROTOCOL, "run_id": run_id, **hello})
            while True:
                remaining = timeout_s - (time.monotonic() - started)
                if remaining <= 0 or not selector.select(remaining):
                    termination, error = "timeout", "wall_time_budget"
                    break
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    if buffer:
                        raise ProtocolError("partial_message")
                    break
                received += len(chunk)
                if received > MAX_OUTPUT:
                    raise ProtocolError("output_budget")
                buffer += chunk
                if b"\n" not in buffer and len(buffer) > MAX_LINE:
                    raise ProtocolError("line_too_long")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    count += 1
                    if count > MAX_MESSAGES:
                        raise ProtocolError("message_budget")
                    try:
                        message = json.loads(line)
                    except ValueError as exc:
                        raise ProtocolError("not_json") from exc
                    if not isinstance(message, dict) or reply is not None:
                        raise ProtocolError("unexpected_message")
                    if message.get("protocol") != PROTOCOL or message.get("run_id") != run_id:
                        raise ProtocolError("protocol_or_run_mismatch")
                    kind = message.get("kind")
                    body = {k: v for k, v in message.items() if k not in ("protocol", "run_id")}
                    allowed = FIELDS.get(kind)
                    # Anything else, such as an event, a score or a guard label the candidate
                    # wants recorded, is refused: the evaluator records its own observations.
                    if allowed is None or not set(body) - {"kind"} <= allowed:
                        raise ProtocolError("unknown_message_schema")
                    if kind == "finish":
                        if not isinstance(body.get("reply"), str):
                            raise ProtocolError("invalid_finish")
                        reply = body["reply"]
                        recorder.add("finish", reply=reply, content_trust="candidate_text")
                        proc.stdin.close()
                        continue
                    send(handlers[kind](body))
            if termination == "finished":
                exit_code = proc.wait(timeout=max(1.0, timeout_s - (time.monotonic() - started)))
                if reply is None:
                    termination = "paused" if recorder.events and _paused(recorder) else "crashed"
                    error = error or "no_finish"
                elif exit_code != 0:
                    termination, error = "crashed", f"exit_{exit_code}"
        except ProtocolError as exc:
            termination, error = "protocol_error", str(exc)
            recorder.add("protocol_violation", error=str(exc))
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired) as exc:
            termination, error = "crashed", f"{type(exc).__name__}: {exc}"
        finally:
            _stop(proc, profile, name)
            exit_code = proc.returncode if exit_code is None else exit_code
            selector.close()
            proc.stdout.close()
            if not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except BrokenPipeError:
                    pass
            stderr.seek(0, os.SEEK_END)
            size = stderr.tell()
            stderr.seek(max(0, size - 4000))
            stderr_tail = stderr.read().decode(errors="replace")
            stderr.close()
    return {
        "duration_s": round(time.monotonic() - recorder.started, 3),
        "reply": reply,
        "termination": termination,
        "error": error,
        "exit_code": exit_code,
        "stderr_tail": stderr_tail,
        "profile": {
            "name": profile,
            "containment": profile == "docker",
            "image": IMAGE if profile == "docker" else None,
            "image_id": image_id,
            "flags": DOCKER_FLAGS if profile == "docker" else ["-I", "empty environment"],
        },
    }


def _paused(recorder: Recorder) -> bool:
    last = [e for e in recorder.events if e["kind"] == "approval"]
    return bool(last) and last[-1].get("decision") is None


def _stop(proc: subprocess.Popen, profile: str, name: str) -> None:
    if profile == "docker":
        # Killing the docker client does not stop the container; remove it by name.
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()


def new_recorder() -> Recorder:
    return Recorder(run_id=str(uuid.uuid4()))
