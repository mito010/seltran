from typing import Any, Callable, Optional, Sequence
from threading import Lock, Event
from queue import Queue, Empty
import tkinter as tk


class UIFuture:
    def __init__(self, fn: Callable, args: tuple, kwargs: dict):
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._result: Any = None
        self._result_lock: Lock = Lock()
        self._finish_event = Event()

    def run(self):
        self._set_result(self._fn(*self._args, **self._kwargs))
        self._set_finished()

    def wait(self) -> Any:
        self._finish_event.wait()
        with self._result_lock:
            return self._result

    def _set_result(self, value: Any):
        with self._result_lock:
            self._result = value

    def _set_finished(self):
        self._finish_event.set()


EVENT_PROCESS_UI_CALLS = "<<ui_call>>"


class TkCallQueue(tk.Tk):
    def __init__(self):
        self._call_queue: Queue[UIFuture] = Queue()
        self.bind(EVENT_PROCESS_UI_CALLS, self._ui_call_handler)

    def _ui_call_handler(self, event: tk.Event):
        try:
            while True:
                call = self._call_queue.get_nowait()
                call.run()
        except Empty:
            pass

    def queue_ui_call(self, fn: Callable, *args, **kwargs) -> UIFuture:
        call = UIFuture(fn, args, kwargs)
        self._call_queue.put(call)
        return call

    def queue_ui_calls(
        self, calls: Sequence[tuple[Callable, Optional[tuple], Optional[dict]]]
    ) -> tuple[UIFuture, ...]:
        return tuple(
            self.queue_ui_call(
                call[0],
                *(call[1] if call[1] else tuple()),
                **(call[2] if call[2] else dict())
            )
            for call in calls
        )

    def signal_process_ui_calls(self):
        self.event_generate(EVENT_PROCESS_UI_CALLS, when="tail")

    def wait_ui_call(self, fn, *args, **kwargs) -> Any:
        call = self.queue_ui_call(fn, *args, **kwargs)
        self.signal_process_ui_calls()
        return call.wait()
