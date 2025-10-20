# python studio_gui/src/qprocess_runner.py
from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QByteArray, Signal, QTimer, QProcessEnvironment
from typing import Optional
import json


class SubprocessController(QObject):
    """Robust QProcess-based subprocess controller.

    Signals:
      - started(): emitted when process starts
      - log_line(stream: str, text: str): emitted per text line read from stdout/stderr
      - parsed_log(object): emitted when a stdout/stderr line parses as JSON (structlog)
      - error(msg: str): emitted on process start/errors
      - finished(exit_code: int, exit_status: int): emitted when process finishes

    Features:
      - UTF-8 decoding with 'replace'
      - Line buffering for partial chunks
      - Graceful terminate with optional grace period (terminate -> kill)
      - Timeout support (seconds)
    """

    started = Signal()
    log_line = Signal(str, str)  # stream, text
    parsed_log = Signal(object)  # parsed JSON object from structlog if any
    error = Signal(str)
    finished = Signal(int, int)  # exit code, exit status (int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._proc = QProcess(self)
        self._stdout_buf = ""
        self._stderr_buf = ""
        self._timeout_timer: Optional[QTimer] = None

        # keep stdout/stderr separate
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.started.connect(self._on_started)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.finished.connect(self._on_finished)

    def start(self, program: str, args: list[str] | None = None, env: dict | None = None,
              cwd: str | None = None, timeout: Optional[int] = None) -> None:
        """Start process. timeout is in seconds (optional).
        env: mapping of env vars to set/override; other vars are preserved.
        """
        args = args or []

        # Merge environment: start from system environment and override with provided env
        qenv = QProcessEnvironment.systemEnvironment()
        if env:
            for k, v in env.items():
                qenv.insert(str(k), str(v))
        self._proc.setProcessEnvironment(qenv)

        if cwd:
            self._proc.setWorkingDirectory(cwd)

        # reset buffers
        self._stdout_buf = ""
        self._stderr_buf = ""

        try:
            self._proc.start(program, args)
        except Exception as e:
            self.error.emit(f"Failed to start process: {e}")
            return

        # Setup timeout
        if timeout and timeout > 0:
            if self._timeout_timer:
                self._timeout_timer.stop()
            self._timeout_timer = QTimer(self)
            self._timeout_timer.setSingleShot(True)
            self._timeout_timer.timeout.connect(lambda: self._on_timeout())
            self._timeout_timer.start(int(timeout * 1000))

    def _on_started(self) -> None:
        self.started.emit()

    def _on_error(self, qerr) -> None:  # QProcess.ProcessError
        try:
            msg = str(qerr)
        except Exception:
            msg = "Unknown QProcess error"
        self.error.emit(msg)

    def _read_bytes(self, data: QByteArray) -> str:
        try:
            b = bytes(data)
            return b.decode("utf-8", errors="replace")
        except Exception:
            try:
                return str(data)
            except Exception:
                return ""

    def _emit_line(self, stream: str, line: str) -> None:
        text = line.rstrip("\r\n")
        self.log_line.emit(stream, text)
        # attempt to parse JSON structured log (structlog JSONRenderer)
        try:
            obj = json.loads(text)
            # prefer to emit dicts only
            if isinstance(obj, dict):
                self.parsed_log.emit(obj)
        except Exception:
            pass

    def _on_stdout(self) -> None:
        data = self._proc.readAllStandardOutput()
        text = self._read_bytes(data)
        if not text:
            return
        combined = self._stdout_buf + text
        lines = combined.splitlines(keepends=True)
        # if last line doesn't end with newline, keep it in buffer
        if lines and not lines[-1].endswith("\n") and not lines[-1].endswith("\r"):
            self._stdout_buf = lines[-1]
            lines = lines[:-1]
        else:
            self._stdout_buf = ""

        for ln in lines:
            self._emit_line("stdout", ln)

    def _on_stderr(self) -> None:
        data = self._proc.readAllStandardError()
        text = self._read_bytes(data)
        if not text:
            return
        combined = self._stderr_buf + text
        lines = combined.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n") and not lines[-1].endswith("\r"):
            self._stderr_buf = lines[-1]
            lines = lines[:-1]
        else:
            self._stderr_buf = ""

        for ln in lines:
            self._emit_line("stderr", ln)

    def _on_timeout(self) -> None:
        # Graceful terminate then kill after short grace period
        if self._proc.state() != QProcess.NotRunning:
            self.log_line.emit("stderr", "[qprocess_runner] Timeout reached, terminating process")
            self.terminate(grace_period=5)

    def _on_finished(self, exitCode: int, exitStatus) -> None:
        # stop timeout timer
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None

        # flush any remaining buffers
        if self._stdout_buf:
            self._emit_line("stdout", self._stdout_buf)
            self._stdout_buf = ""
        if self._stderr_buf:
            self._emit_line("stderr", self._stderr_buf)
            self._stderr_buf = ""

        try:
            status_int = int(exitStatus)
        except Exception:
            try:
                status_int = int(exitStatus.value)  # fallback
            except Exception:
                status_int = 0

        self.finished.emit(int(exitCode), status_int)

    def terminate(self, grace_period: int = 5) -> None:
        """Attempt polite termination, then force kill after grace_period seconds."""
        if self._proc.state() == QProcess.NotRunning:
            return
        try:
            self._proc.terminate()
        except Exception:
            pass

        # schedule kill if still running
        def _kill_if_running():
            if self._proc.state() != QProcess.NotRunning:
                try:
                    self._proc.kill()
                except Exception:
                    pass

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(_kill_if_running)
        timer.start(grace_period * 1000)

    def kill(self) -> None:
        if self._proc.state() != QProcess.NotRunning:
            try:
                self._proc.kill()
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.NotRunning

    def pid(self) -> int:
        try:
            return int(self._proc.processId())
        except Exception:
            return 0
