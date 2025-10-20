from __future__ import annotations

import sys
import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class ProcessEvent:
    stream: str  # "stdout" | "stderr"
    line: str


class ProcessRunner:
    """Async subprocess runner with merged, line-based stdout/stderr streaming.

    Windows/PowerShell safe. Produces UTF-8 text lines and exposes a safe timeout
    and cancellation API for use in higher-level orchestration.
    """

    def __init__(self, cmd: list[str], cwd: Optional[str] = None, env: Optional[dict[str, str]] = None) -> None:
        self.cmd = cmd
        self.cwd = cwd
        # Ensure a copy of env to avoid mutating caller's dict
        self.env = dict(env) if env else None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._cancelled = False

    async def start(self) -> None:
        # On Windows, creationflags could set CREATE_NEW_PROCESS_GROUP for signal handling
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0

        self._proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )

    async def iter_lines(self) -> AsyncIterator[ProcessEvent]:
        assert self._proc and self._proc.stdout and self._proc.stderr

        async def reader(stream: asyncio.StreamReader, name: str, q: asyncio.Queue[ProcessEvent]):
            while True:
                line = await stream.readline()
                if not line:
                    break
                try:
                    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    text = line.decode(errors="replace").rstrip("\r\n")
                await q.put(ProcessEvent(name, text))

        q: asyncio.Queue[ProcessEvent] = asyncio.Queue()
        t_out = asyncio.create_task(reader(self._proc.stdout, "stdout", q))
        t_err = asyncio.create_task(reader(self._proc.stderr, "stderr", q))

        pending = {t_out, t_err}
        try:
            while pending:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=0.05)
                    yield evt
                except asyncio.TimeoutError:
                    if all(t.done() for t in pending):
                        break
                    pending = {t for t in pending if not t.done()}
        finally:
            # Ensure reader tasks are awaited to avoid warnings
            await asyncio.gather(t_out, t_err, return_exceptions=True)

    async def wait(self) -> int:
        assert self._proc
        return await self._proc.wait()

    async def run_collect(self, timeout: Optional[float] = None) -> tuple[int, list[ProcessEvent]]:
        await self.start()
        events: list[ProcessEvent] = []
        try:
            async for evt in self.iter_lines():
                events.append(evt)
            if timeout:
                code = await asyncio.wait_for(self.wait(), timeout=timeout)
            else:
                code = await self.wait()
        except asyncio.TimeoutError:
            # attempt graceful termination
            if self._proc and self._proc.returncode is None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=5)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
            code = self._proc.returncode if self._proc else -1
        finally:
            return code, events
