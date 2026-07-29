import asyncio
import sys
import threading
import time
import traceback
from logging import Logger

try:
    time.thread_time_ns()
    _thread_time_ns = time.thread_time_ns
except AttributeError, OSError:
    # thread_time_ns() isn't available on every platform; process_time_ns()
    # still works, at the cost of executor threads inflating the CPU number
    _thread_time_ns = time.process_time_ns


class LoopWatchdog:
    """Detects event-loop stalls and points at the offending call stack.

    `loop.slow_callback_duration` alone can only report the line where the
    coroutine is suspended (the next `await`), not the line that actually
    burned the time, and can't distinguish CPU-bound work from blocking
    calls (`time.sleep`, sync I/O, sync DNS). This samples the main thread's
    stack from a separate watchdog thread while it's stalled, and classifies
    each stall as CPU-bound vs blocking via thread CPU time.

    Known blind spot: a `@njit` function (without `nogil=True`) or any C
    extension holding the GIL prevents the watchdog thread from sampling
    until it releases the GIL, so the reported stack points at the line
    *after* the call rather than into it. The stall duration and CPU
    classification are still correct. `py-spy dump --native` is the
    fallback for those (needs Developer Tools permission on macOS).
    """

    def __init__(
        self, logger: Logger, threshold: float = 0.05, interval: float = 0.005
    ) -> None:
        self.logger = logger
        self.threshold_ns = int(threshold * 1e9)
        self.interval = interval
        self.tid = threading.get_ident()
        self.beat_ns = time.perf_counter_ns()
        self.beat_cpu = _thread_time_ns()
        self.stack: str | None = None
        self._stop = False

    async def heartbeat(self) -> None:
        while not self._stop:
            now, cpu = time.perf_counter_ns(), _thread_time_ns()
            wall_d, cpu_d = now - self.beat_ns, cpu - self.beat_cpu
            if wall_d >= self.threshold_ns:
                kind = "CPU-BOUND" if cpu_d > 0.7 * wall_d else "BLOCKING/not-cpu"
                self.logger.warning(
                    f"loop stall {wall_d / 1e6:.0f}ms (cpu {cpu_d / 1e6:.0f}ms) {kind}\n"
                    f"{self.stack or '  <no sample>'}"
                )
            self.stack = None
            self.beat_ns, self.beat_cpu = time.perf_counter_ns(), _thread_time_ns()
            await asyncio.sleep(self.interval)

    def _watch(self) -> None:
        # runs on a plain thread, not the event loop, so it can sample the
        # main thread's stack *while* the loop is stalled
        while not self._stop:
            time.sleep(self.interval)
            if time.perf_counter_ns() - self.beat_ns < self.threshold_ns or self.stack:
                continue
            frame = sys._current_frames().get(self.tid)
            if frame is not None:
                self.stack = "".join(traceback.format_stack(frame)[-3:])

    def stop(self) -> None:
        self._stop = True

    def start(self) -> asyncio.Task:
        threading.Thread(target=self._watch, daemon=True, name="loop-watchdog").start()
        return asyncio.create_task(self.heartbeat(), name="loop-watchdog-heartbeat")
