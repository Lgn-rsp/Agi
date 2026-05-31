"""dynamical_brain.py — continuously-running integration loop.

This is the replacement for `night_learn.cycle()`. Instead of:

  while RUNNING:
      brain.cycle()        # read JSON, compute, write JSON
      sleep(N seconds)

we have:

  brain = DynamicalBrain(network, binding, integration_hz=200)
  brain.start()             # thread now integrates 200×/sec
  ...
  brain.observe("hello")   # pushes drive into next step
  phase = brain.phase("hello")  # reads live state, no disk
  ...
  brain.stop()

The state is the oscillator network. It evolves continuously. Modules from
the existing LOGOS codebase migrate one at a time to read state via the
binding instead of reading JSON.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from phi_resonance.oscillator_network import (
    KuramotoNetwork,
    StuartLandauNetwork,
)
from phi_resonance.symbol_binding import SymbolBinding

TAU = 2.0 * np.pi


class DynamicalBrain:
    """Background-thread runtime around a coupled-oscillator network.

    integration_hz: target steps per second (real wall time). The actual
        simulated time per step is the network's `dt`, so simulated/wall
        ratio = integration_hz × dt. Default 200 Hz with dt=0.01 → 2× real
        time (network sees 2 seconds of dynamics per real second). Pick dt
        and integration_hz together.

    Thread safety:
        - All access to network state goes through self._lock.
        - `observe()`, `phase()`, `snapshot()` are safe to call from any
          thread.
    """

    def __init__(
        self,
        network: KuramotoNetwork | StuartLandauNetwork,
        binding: SymbolBinding,
        integration_hz: float = 200.0,
    ):
        self.net = network
        self.binding = binding
        self.target_period = 1.0 / float(integration_hz)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self.steps_executed = 0
        self.last_step_wall_ms = 0.0

    # ----- lifecycle -----

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="phi_brain",
                                          daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ----- integration loop -----

    def _loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.perf_counter()
            with self._lock:
                drive = self.binding.consume_drive()
                self.net.step()
                # Apply external drive as an extra phase increment on top
                # of the dynamics step. Magnitude is dt × drive.
                if drive.any():
                    self.net.theta = (
                        self.net.theta + self.net.dt * drive
                    ) % TAU
                self.steps_executed += 1
            elapsed = time.perf_counter() - t0
            self.last_step_wall_ms = elapsed * 1000.0
            sleep_time = self.target_period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            # If sleep_time < 0 we are running slower than target_hz; just
            # continue immediately. Don't try to "catch up" by skipping
            # steps — accumulating phase drift is worse than running slow.

    # ----- thread-safe API for external modules -----

    def observe(self, symbol: str, drive: float = 1.0) -> None:
        with self._lock:
            self.binding.observe(symbol, drive)

    def phase(self, symbol: str) -> float:
        with self._lock:
            return self.binding.phase(symbol)

    def amplitude(self, symbol: str) -> float:
        with self._lock:
            return self.binding.amplitude(symbol)

    def nearest(self, symbol: str, k: int = 8) -> list[tuple[str, float]]:
        with self._lock:
            return self.binding.nearest(symbol, k=k)

    def synchronized_cluster(self, symbol: str,
                              tolerance: float = 0.1) -> list[str]:
        with self._lock:
            return self.binding.synchronized_cluster(symbol, tolerance=tolerance)

    def order_parameter(self) -> float:
        from phi_resonance.observables import order_parameter
        with self._lock:
            R, _ = order_parameter(self.net.theta[: len(self.binding)])
        return R

    def snapshot(self) -> dict:
        with self._lock:
            return self.binding.snapshot()

    # ----- introspection -----

    def stats(self) -> dict:
        return {
            "running": self.is_running(),
            "steps_executed": self.steps_executed,
            "last_step_wall_ms": round(self.last_step_wall_ms, 3),
            "target_period_ms": round(self.target_period * 1000.0, 3),
            "sim_time": float(self.net.t),
            "n_bound": len(self.binding),
            "network_size": self.net.N,
        }
