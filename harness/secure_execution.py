"""Fail-closed Docker execution for untrusted candidate implementations."""
from __future__ import annotations

import json
import os
import selectors
import signal
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SANDBOX_IMAGE = "python:3.11.18-slim-bookworm@sha256:ef521de1d817dc92a6358c906bbadb9a0b7e38040038642833521b9d582c2233"
RUNTIME = ROOT / "harness" / "candidate_runtime.py"


class SecureExecutionUnavailable(RuntimeError):
    """Raised when the required Docker isolation cannot be established."""

    secure_unavailable = True


class CandidateExecutionError(RuntimeError):
    """A candidate failed, timed out, or returned a malformed runtime response."""


def docker_preflight(image: str = SANDBOX_IMAGE) -> dict[str, Any]:
    """Require a working daemon and a locally available pinned image; never fall back or pull."""
    docker = shutil.which("docker")
    if not docker:
        raise SecureExecutionUnavailable("secure model evaluation unavailable: Docker CLI is not installed")
    daemon = subprocess.run([docker, "info"], capture_output=True, text=True, timeout=10, check=False)
    if daemon.returncode:
        detail = (daemon.stderr or daemon.stdout).strip().splitlines()
        raise SecureExecutionUnavailable(
            "secure model evaluation unavailable: Docker daemon is unavailable"
            + (f" ({detail[-1]})" if detail else "")
        )
    inspected = subprocess.run([docker, "image", "inspect", image], capture_output=True, text=True, timeout=10, check=False)
    if inspected.returncode:
        raise SecureExecutionUnavailable(
            f"secure model evaluation unavailable: pinned sandbox image {image!r} is not present locally; "
            f"pull it explicitly with `docker pull {image}` when an isolated Docker daemon is available"
        )
    try:
        details = json.loads(inspected.stdout)[0]
    except (ValueError, IndexError, TypeError):
        details = {}
    # Exercise the exact restrictive option set with trusted, trivial code before any model call.
    with tempfile.TemporaryDirectory(prefix="senseline-docker-probe-") as temp:
        probe_source = Path(temp) / "solution.py"
        probe_source.write_text("def solve(payload):\n    return payload\n", encoding="utf-8")
        probe_name = "senseline-probe-" + uuid.uuid4().hex[:16]
        command = docker_command(probe_source, RUNTIME, probe_name, image)
        try:
            probe = subprocess.run(command, input='{"probe":"isolation"}\n', capture_output=True, text=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            for args in ([docker, "kill", probe_name], [docker, "rm", "--force", probe_name]):
                try: subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
                except (OSError, subprocess.TimeoutExpired): pass
            raise SecureExecutionUnavailable(f"secure model evaluation unavailable: Docker isolation probe failed ({exc})") from exc
        if probe.returncode != 0:
            raise SecureExecutionUnavailable(
                "secure model evaluation unavailable: Docker rejected one or more required isolation controls: "
                f"{(probe.stderr or probe.stdout).strip()[-2000:]}"
            )
        try:
            rows = [json.loads(line) for line in probe.stdout.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise SecureExecutionUnavailable("secure model evaluation unavailable: Docker isolation probe returned malformed output") from exc
        if len(rows) != 1 or rows[0].get("ok") is not True or rows[0].get("output") != {"probe": "isolation"}:
            raise SecureExecutionUnavailable("secure model evaluation unavailable: pinned Python runtime/isolation probe did not pass")
    return {"docker_path": docker, "image": image, "image_id": details.get("Id"), "isolation": "docker", "isolation_probe": "PASS"}


def docker_command(candidate: Path, runner: Path, container_name: str, image: str = SANDBOX_IMAGE, support_mounts=()) -> list[str]:
    """Construct the complete restrictive `docker run` argv used for every input."""
    command = [
        shutil.which("docker") or "docker", "run", "--rm", "--interactive", "--name", container_name, "--log-driver=none",
        "--network=none", "--user=65534:65534", "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true", "--read-only",
        "--pids-limit=32", "--memory=128m", "--memory-swap=128m", "--cpus=0.50",
        "--ulimit=nofile=64:64", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
        "--mount", f"type=bind,src={candidate.resolve()},dst=/candidate/solution.py,readonly",
        "--mount", f"type=bind,src={runner.resolve()},dst=/runtime/runner.py,readonly",
        "--workdir=/candidate", "--env=PYTHONDONTWRITEBYTECODE=1",
    ]
    for host_path, container_path in support_mounts:
        command.extend(["--mount", f"type=bind,src={Path(host_path).resolve()},dst={container_path},readonly"])
    if support_mounts:
        command.append("--env=PYTHONPATH=/support")
    command.extend([image, "python", "/runtime/runner.py", "/candidate/solution.py"])
    return command


class DockerCandidate:
    """Callable candidate facade. Each solve gets one isolated container and one JSON input."""

    def __init__(
        self,
        source: str | Path,
        timeout_seconds: float = 5.0,
        image: str = SANDBOX_IMAGE,
        event_sink=None,
        preflight: dict[str, Any] | None = None,
        support_mounts=(),
    ) -> None:
        self.source = Path(source).resolve()
        self.timeout_seconds = timeout_seconds
        self.image = image
        self.event_sink = event_sink
        self.support_mounts = tuple(support_mounts)
        if not self.source.is_file():
            raise SecureExecutionUnavailable(f"candidate source does not exist: {self.source}")
        if not RUNTIME.is_file():
            raise SecureExecutionUnavailable(f"trusted candidate runtime is missing: {RUNTIME}")
        self.isolation = preflight or docker_preflight(image)

    def solve(self, payload: dict) -> Any:
        docker = str(self.isolation.get("docker_path") or shutil.which("docker") or "docker")
        name = "senseline-" + uuid.uuid4().hex[:20]
        command = docker_command(self.source, RUNTIME, name, self.image, self.support_mounts)
        try:
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        except (TypeError, ValueError) as exc:
            raise CandidateExecutionError(f"input is not JSON serializable: {exc}") from exc
        try:
            stdout, stderr, exit_code = self._bounded_run(command, encoded, docker, name)
        except TimeoutError as exc:
            raise CandidateExecutionError(f"candidate exceeded {self.timeout_seconds:g}s execution limit") from exc
        except CandidateExecutionError:
            raise
        except OSError as exc:
            raise SecureExecutionUnavailable(f"secure candidate runner could not start Docker: {exc}") from exc
        if exit_code != 0:
            if exit_code in (125, 126, 127):
                raise SecureExecutionUnavailable(
                    "secure model evaluation unavailable: Docker could not start the pinned, restricted container: "
                    f"{(stderr or stdout).strip()[-2000:]}"
                )
            raise CandidateExecutionError(
                f"isolated candidate process exited {exit_code}: "
                f"{(stderr or stdout).strip()[-2000:]}"
            )
        lines = [line for line in stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise CandidateExecutionError("isolated candidate did not emit exactly one JSON response")
        try:
            record = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise CandidateExecutionError(f"isolated candidate emitted malformed JSON: {exc}") from exc
        event = {
            "event": "candidate_execution_completed" if record.get("ok") else "candidate_execution_failed",
            "container_name": name,
            "timeout_seconds": self.timeout_seconds,
            "exit_code": exit_code,
            "candidate_stdout": record.get("candidate_stdout", ""),
            "candidate_stderr": record.get("candidate_stderr", ""),
            "output": record.get("output"),
            "error": record.get("error"),
            "container_stderr": stderr,
        }
        if self.event_sink:
            self.event_sink(event)
        self.last_candidate_stdout = record.get("candidate_stdout", "")
        self.last_candidate_stderr = record.get("candidate_stderr", "")
        if not record.get("ok"):
            failure = CandidateExecutionError(record.get("error", "candidate execution failed"))
            failure.candidate_stdout = self.last_candidate_stdout
            failure.candidate_stderr = self.last_candidate_stderr
            raise failure
        return record.get("output")

    def _bounded_run(self, command: list[str], encoded: str, docker: str, name: str):
        """Capture bounded output and enforce a hard wall timeout around the Docker client."""
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {"stdout": 2 * 1024 * 1024, "stderr": 512 * 1024}
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            process.stdin.write(encoded.encode("utf-8"))
            process.stdin.close()
            deadline = time.monotonic() + self.timeout_seconds
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("candidate timeout")
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = buffers[key.data]
                    buffer.extend(chunk)
                    if len(buffer) > limits[key.data]:
                        raise CandidateExecutionError(f"candidate {key.data} exceeded {limits[key.data]} byte output limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                raise TimeoutError("candidate timeout")
            exit_code = process.wait(timeout=max(0.05, remaining))
            return buffers["stdout"].decode("utf-8", errors="replace"), buffers["stderr"].decode("utf-8", errors="replace"), exit_code
        except (TimeoutError, CandidateExecutionError):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._stop_container(docker, name)
            process.wait(timeout=5)
            raise
        finally:
            selector.close()
            for handle in (process.stdin, process.stdout, process.stderr):
                if handle and not handle.closed:
                    handle.close()

    @staticmethod
    def _stop_container(docker: str, name: str) -> None:
        for args in ([docker, "kill", name], [docker, "rm", "--force", name]):
            try:
                subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
