from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
DEFAULT_TRACE_PATH = ROOT_DIR / "experiments" / "replay_profiles" / "heterogeneous_fault_trace.csv"
DEFAULT_TRACE_EVENTS_PATH = ROOT_DIR / "experiments" / "replay_profiles" / "heterogeneous_fault_events.csv"
LATEST_EVALUATION_DIR = ROOT_DIR / "experiments" / "evaluation" / "latest"
GUI_RUNS_DIR = ROOT_DIR / "experiments" / "gui_runs"
LIVE_RUNS_DIR = ROOT_DIR / "experiments" / "live_runs"


class ControlBusyError(RuntimeError):
    """Raised when the caller tries to start a second long-running job."""


class NoActiveJobError(RuntimeError):
    """Raised when the caller tries to cancel a non-existent job."""


class JobCancelledError(RuntimeError):
    """Raised internally when a running subprocess is cancelled."""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


@dataclass
class JobStep:
    key: str
    label: str
    status: str = "pending"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
        }


@dataclass
class JobState:
    kind: str
    title: str
    parameters: dict[str, Any]
    steps: list[JobStep]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    current_step: Optional[str] = None
    cancel_requested: bool = False
    active_pid: Optional[int] = None
    artifacts: dict[str, str] = field(default_factory=dict)
    log_lines: deque[str] = field(default_factory=lambda: deque(maxlen=320))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "current_step": self.current_step,
            "cancel_requested": self.cancel_requested,
            "active_pid": self.active_pid,
            "parameters": self.parameters,
            "steps": [step.to_dict() for step in self.steps],
            "artifacts": self.artifacts,
            "log_lines": list(self.log_lines),
        }


class ExperimentControlService:
    """Runs long-lived experiment jobs in the background for the UI console."""

    def __init__(self) -> None:
        self._started_at = _now_iso()
        self._python_path = self._resolve_python_path()
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}
        self._recent_job_ids: deque[str] = deque(maxlen=8)
        self._active_job_id: Optional[str] = None
        self._current_process: Optional[subprocess.Popen[str]] = None

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            active_job = self._jobs.get(self._active_job_id) if self._active_job_id else None
            recent_jobs = [self._jobs[job_id].to_dict() for job_id in reversed(self._recent_job_ids)]

        return {
            "service": {
                "started_at": self._started_at,
                "python_path": str(self._python_path),
                "frontend_dist_ready": (FRONTEND_DIST_DIR / "index.html").exists(),
                "frontend_dist_path": str(FRONTEND_DIST_DIR),
            },
            "trace": self._build_file_state(DEFAULT_TRACE_PATH, DEFAULT_TRACE_EVENTS_PATH),
            "latest_report": self._build_file_state(
                LATEST_EVALUATION_DIR / "report.json",
                LATEST_EVALUATION_DIR / "report.md",
            ),
            "active_job": active_job.to_dict() if active_job else None,
            "recent_jobs": recent_jobs,
        }

    def start_trace_generation(self, *, duration: float, step: float, seed: int) -> dict[str, Any]:
        job = JobState(
            kind="trace_generation",
            title="Generate Replay Trace",
            parameters={
                "duration": duration,
                "step": step,
                "seed": seed,
            },
            steps=[JobStep(key="generate_trace", label="Generate replay trace")],
        )

        def runner(target: JobState) -> None:
            DEFAULT_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._run_command(
                target,
                target.steps[0],
                [
                    str(self._python_path),
                    "demo/generate_replay_trace.py",
                    "--output",
                    str(DEFAULT_TRACE_PATH),
                    "--events-output",
                    str(DEFAULT_TRACE_EVENTS_PATH),
                    "--duration",
                    str(duration),
                    "--step",
                    str(step),
                    "--seed",
                    str(seed),
                ],
            )
            target.artifacts.update(
                {
                    "trace_csv": _safe_relative(DEFAULT_TRACE_PATH),
                    "events_csv": _safe_relative(DEFAULT_TRACE_EVENTS_PATH),
                }
            )

        self._launch_job(job, runner)
        return job.to_dict()

    def start_replay_compare(
        self,
        *,
        base_url: str,
        devices: str,
        gpu_vendor: str,
        npu_backend: str,
        duration: float,
        fixed_interval: float,
        t_min: float,
        t_max: float,
        regenerate_trace: bool,
        trace_duration: float,
        trace_step: float,
        trace_seed: int,
    ) -> dict[str, Any]:
        should_generate_trace = regenerate_trace or not DEFAULT_TRACE_PATH.exists()
        steps: list[JobStep] = []
        if should_generate_trace:
            steps.append(JobStep(key="generate_trace", label="Prepare replay trace"))
        steps.extend(
            [
                JobStep(key="run_fixed", label="Run fixed-frequency experiment"),
                JobStep(key="run_evolution", label="Run evolution experiment"),
                JobStep(key="evaluate", label="Evaluate and publish report"),
            ]
        )

        job = JobState(
            kind="replay_compare",
            title="Replay Compare Evaluation",
            parameters={
                "devices": devices,
                "gpu_vendor": gpu_vendor,
                "npu_backend": npu_backend,
                "duration": duration,
                "fixed_interval": fixed_interval,
                "t_min": t_min,
                "t_max": t_max,
                "regenerate_trace": should_generate_trace,
            },
            steps=steps,
        )

        def runner(target: JobState) -> None:
            GUI_RUNS_DIR.mkdir(parents=True, exist_ok=True)
            run_dir = GUI_RUNS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
            data_dir = run_dir / "data"
            report_snapshot_dir = run_dir / "report"
            data_dir.mkdir(parents=True, exist_ok=True)
            report_snapshot_dir.mkdir(parents=True, exist_ok=True)
            LATEST_EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

            step_map = {step.key: step for step in target.steps}

            if should_generate_trace:
                self._run_command(
                    target,
                    step_map["generate_trace"],
                    [
                        str(self._python_path),
                        "demo/generate_replay_trace.py",
                        "--output",
                        str(DEFAULT_TRACE_PATH),
                        "--events-output",
                        str(DEFAULT_TRACE_EVENTS_PATH),
                        "--duration",
                        str(trace_duration),
                        "--step",
                        str(trace_step),
                        "--seed",
                        str(trace_seed),
                    ],
                )

            fixed_csv = data_dir / "fixed_metrics.csv"
            fixed_events = data_dir / "fixed_events.csv"
            fixed_db = data_dir / "fixed_outbox.db"
            evolution_csv = data_dir / "evolution_metrics.csv"
            evolution_events = data_dir / "evolution_events.csv"
            evolution_db = data_dir / "evolution_outbox.db"
            report_json = LATEST_EVALUATION_DIR / "report.json"
            report_md = LATEST_EVALUATION_DIR / "report.md"

            shared_args = [
                str(self._python_path),
                "demo/evolution_sampling_experiment.py",
                "--device",
                devices,
                "--vendor",
                gpu_vendor,
                "--npu-backend",
                npu_backend,
                "--trace-file",
                str(DEFAULT_TRACE_PATH),
                "--duration",
                str(duration),
                "--remote-endpoint",
                f"{base_url}/api/ingest",
            ]

            self._run_command(
                target,
                step_map["run_fixed"],
                [
                    *shared_args,
                    "--mode",
                    "fixed",
                    "--fixed-interval",
                    str(fixed_interval),
                    "--output",
                    str(fixed_csv),
                    "--event-output",
                    str(fixed_events),
                    "--outbox-db",
                    str(fixed_db),
                ],
            )

            self._run_command(
                target,
                step_map["run_evolution"],
                [
                    *shared_args,
                    "--mode",
                    "evolution",
                    "--t-min",
                    str(t_min),
                    "--t-max",
                    str(t_max),
                    "--output",
                    str(evolution_csv),
                    "--event-output",
                    str(evolution_events),
                    "--outbox-db",
                    str(evolution_db),
                ],
            )

            evaluate_args = [
                str(self._python_path),
                "demo/evaluate_metrics.py",
                "--fixed",
                str(fixed_csv),
                "--evolution",
                str(evolution_csv),
                "--output-dir",
                str(LATEST_EVALUATION_DIR),
            ]
            if DEFAULT_TRACE_EVENTS_PATH.exists():
                evaluate_args.extend(["--ground-truth-events", str(DEFAULT_TRACE_EVENTS_PATH)])

            self._run_command(target, step_map["evaluate"], evaluate_args)

            if report_json.exists():
                shutil.copy2(report_json, report_snapshot_dir / "report.json")
            if report_md.exists():
                shutil.copy2(report_md, report_snapshot_dir / "report.md")

            target.artifacts.update(
                {
                    "run_dir": _safe_relative(run_dir),
                    "fixed_csv": _safe_relative(fixed_csv),
                    "evolution_csv": _safe_relative(evolution_csv),
                    "report_json": _safe_relative(report_json),
                    "report_md": _safe_relative(report_md),
                }
            )

        self._launch_job(job, runner)
        return job.to_dict()

    def start_live_collection(
        self,
        *,
        base_url: str,
        devices: str,
        gpu_vendor: str,
        npu_backend: str,
        mode: str,
        duration: float,
        fixed_interval: float,
        t_min: float,
        t_max: float,
    ) -> dict[str, Any]:
        job = JobState(
            kind="live_collection",
            title="Live Collection",
            parameters={
                "devices": devices,
                "gpu_vendor": gpu_vendor,
                "npu_backend": npu_backend,
                "mode": mode,
                "duration": duration,
                "fixed_interval": fixed_interval,
                "t_min": t_min,
                "t_max": t_max,
            },
            steps=[JobStep(key="run_live_collection", label="Collect current machine metrics")],
        )

        def runner(target: JobState) -> None:
            LIVE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
            run_dir = LIVE_RUNS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
            data_dir = run_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            metrics_csv = data_dir / f"{mode}_metrics.csv"
            events_csv = data_dir / f"{mode}_events.csv"
            outbox_db = data_dir / f"{mode}_outbox.db"

            command = [
                str(self._python_path),
                "demo/evolution_sampling_experiment.py",
                "--mode",
                mode,
                "--device",
                devices,
                "--vendor",
                gpu_vendor,
                "--npu-backend",
                npu_backend,
                "--duration",
                str(duration),
                "--output",
                str(metrics_csv),
                "--event-output",
                str(events_csv),
                "--outbox-db",
                str(outbox_db),
                "--remote-endpoint",
                f"{base_url}/api/ingest",
            ]
            if mode == "fixed":
                command.extend(["--fixed-interval", str(fixed_interval)])
            else:
                command.extend(["--t-min", str(t_min), "--t-max", str(t_max)])

            self._run_command(target, target.steps[0], command)
            target.artifacts.update(
                {
                    "run_dir": _safe_relative(run_dir),
                    "metrics_csv": _safe_relative(metrics_csv),
                    "events_csv": _safe_relative(events_csv),
                    "outbox_db": _safe_relative(outbox_db),
                }
            )

        self._launch_job(job, runner)
        return job.to_dict()

    def cancel_active_job(self) -> dict[str, Any]:
        with self._lock:
            if not self._active_job_id:
                raise NoActiveJobError("no active job to cancel")

            job = self._jobs[self._active_job_id]
            job.cancel_requested = True
            process = self._current_process
            if process and process.poll() is None:
                process.terminate()

            self._append_log_locked(job, "Cancellation requested by user.")
            return job.to_dict()

    def _launch_job(self, job: JobState, runner: Callable[[JobState], None]) -> None:
        with self._lock:
            if self._active_job_id:
                raise ControlBusyError("another job is already running")
            self._jobs[job.id] = job
            self._recent_job_ids.append(job.id)
            self._active_job_id = job.id
            self._append_log_locked(job, f"Job queued: {job.title}")

        thread = threading.Thread(target=self._run_job, args=(job.id, runner), daemon=True)
        thread.start()

    def _run_job(self, job_id: str, runner: Callable[[JobState], None]) -> None:
        job = self._jobs[job_id]
        with self._lock:
            job.status = "running"
            job.started_at = _now_iso()
            self._append_log_locked(job, "Job started.")

        try:
            runner(job)
            with self._lock:
                if job.cancel_requested:
                    job.status = "cancelled"
                    self._append_log_locked(job, "Job cancelled.")
                else:
                    job.status = "succeeded"
                    self._append_log_locked(job, "Job completed successfully.")
                job.current_step = None
                job.finished_at = _now_iso()
        except JobCancelledError:
            with self._lock:
                job.status = "cancelled"
                job.current_step = None
                job.finished_at = _now_iso()
                self._append_log_locked(job, "Job cancelled while running.")
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                job.status = "failed"
                job.error = str(exc)
                job.current_step = None
                job.finished_at = _now_iso()
                self._append_log_locked(job, f"Job failed: {exc}")
        finally:
            with self._lock:
                self._active_job_id = None
                self._current_process = None
                job.active_pid = None

    def _run_command(self, job: JobState, step: JobStep, args: list[str]) -> None:
        if job.cancel_requested:
            raise JobCancelledError("job cancelled before step started")

        with self._lock:
            step.status = "running"
            step.started_at = _now_iso()
            job.current_step = step.label
            self._append_log_locked(job, f"$ {' '.join(args)}")

        process = subprocess.Popen(
            args,
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=self._build_process_env(),
        )

        with self._lock:
            self._current_process = process
            job.active_pid = process.pid

        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    with self._lock:
                        self._append_log_locked(job, line)
                    if job.cancel_requested and process.poll() is None:
                        process.terminate()

            exit_code = process.wait()
        finally:
            with self._lock:
                self._current_process = None
                job.active_pid = None

        with self._lock:
            step.exit_code = exit_code
            step.finished_at = _now_iso()

        if job.cancel_requested:
            with self._lock:
                step.status = "cancelled"
            raise JobCancelledError(f"step {step.key} was cancelled")

        if exit_code != 0:
            with self._lock:
                step.status = "failed"
            raise RuntimeError(f"{step.label} exited with code {exit_code}")

        with self._lock:
            step.status = "succeeded"

    def _resolve_python_path(self) -> Path:
        candidates = [
            ROOT_DIR / ".venv" / "Scripts" / "python.exe",
            ROOT_DIR / ".venv" / "bin" / "python",
            Path(sys.executable),
        ]
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate

        python_name = shutil.which("python")
        if python_name:
            return Path(python_name)

        raise FileNotFoundError("Python executable was not found. Create .venv or add python to PATH.")

    def _build_process_env(self) -> dict[str, str]:
        env = os.environ.copy()
        # Force child Python processes to emit UTF-8 so the web console can display
        # Chinese phase names, alerts, and evaluation summaries without mojibake.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _build_file_state(self, primary: Path, secondary: Optional[Path] = None) -> dict[str, Any]:
        state = {
            "exists": primary.exists(),
            "path": _safe_relative(primary),
            "updated_at": None,
            "size_bytes": None,
            "secondary_path": _safe_relative(secondary) if secondary else None,
            "secondary_exists": secondary.exists() if secondary else None,
        }
        if primary.exists():
            stat = primary.stat()
            state["updated_at"] = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
            state["size_bytes"] = stat.st_size
        return state

    def _append_log_locked(self, job: JobState, line: str) -> None:
        job.log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")


control_service = ExperimentControlService()
