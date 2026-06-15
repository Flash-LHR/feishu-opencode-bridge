from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class EventWorker:
    def __init__(self, handler: Callable[[object], None], workers: int = 2) -> None:
        self._handler = handler
        self._workers = max(1, workers)
        self._queue: "queue.Queue[Optional[object]]" = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self._workers):
            thread = threading.Thread(
                target=self._run,
                name=f"feishu-opencode-worker-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def submit(self, event: object) -> None:
        if not self._started:
            self.start()
        self._queue.put(event)

    def stop(self, timeout: float = 5.0) -> None:
        if not self._started:
            return
        for _ in self._threads:
            self._queue.put(None)
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()
        self._started = False

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            try:
                if event is None:
                    return
                self._handler(event)
            except Exception:
                logger.exception("Unhandled worker error")
            finally:
                self._queue.task_done()
