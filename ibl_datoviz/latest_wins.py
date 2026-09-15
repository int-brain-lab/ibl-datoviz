"""Small, renderer-independent latest-wins asynchronous preparation queue.

``LatestWinsExecutor`` is intended for work such as decoding a requested atlas
slice.  Preparation runs on worker threads, while callers retain ownership of
the result and may apply it to scene state from their own thread.  A key (for
example, an axis) has at most one active preparation loop and one pending
request; a newer request supersedes both an older pending request and an older
ready result.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

Key = TypeVar('Key', bound=object)
Token = TypeVar('Token', bound=object)
Result = TypeVar('Result', bound=object)


@dataclass(frozen=True)
class ReadyResult(Generic[Key, Token, Result]):
    """A prepared result waiting for its owner to consume it."""

    key: Key
    token: Token
    result: Result


@dataclass
class _State(Generic[Token, Result]):
    generation: int = 0
    active: bool = False
    pending: tuple[int, Token] | None = None
    ready: ReadyResult[object, Token, Result] | None = None
    error: Exception | None = None


class LatestWinsExecutor(Generic[Key, Token, Result]):
    """Prepare at most the newest request for each key in worker threads.

    Parameters
    ----------
    prepare:
        Pure preparation function.  It is called with a request token and
        must return a result; it must not mutate renderer or scene state.
    notify:
        Optional wake-up callback called with a key after a current result (or
        failure) becomes ready.  The callback is deliberately not given a
        result, and should only arrange for the owner thread to call
        :meth:`drain_ready`.
    max_workers:
        Maximum number of worker threads.  A worker handles one key at a time;
        independent keys can therefore progress concurrently.
    """

    def __init__(
        self,
        prepare: Callable[[Token], Result],
        *,
        notify: Callable[[Key], object] | None = None,
        max_workers: int = 2,
    ) -> None:
        if max_workers < 1:
            raise ValueError('max_workers must be positive')
        self._prepare = prepare
        self._notify = notify
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = RLock()
        self._states: dict[Key, _State[Token, Result]] = {}
        self._closed = False

    def request(self, key: Key, token: Token) -> None:
        """Submit or supersede a request for ``key``.

        Tokens are treated as immutable by this class.  Calling ``request``
        after :meth:`close` raises ``RuntimeError``.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError('latest-wins executor is closed')
            state = self._states.setdefault(key, _State())
            state.generation += 1
            state.pending = (state.generation, token)
            state.ready = None
            state.error = None
            if not state.active:
                state.active = True
                self._executor.submit(self._run, key)

    def _run(self, key: Key) -> None:
        while True:
            with self._lock:
                state = self._states.get(key)
                if state is None or state.pending is None:
                    if state is not None:
                        state.active = False
                    return
                generation, token = state.pending
                state.pending = None
                closing = self._closed
            if closing:
                with self._lock:
                    state = self._states.get(key)
                    if state is not None:
                        state.active = False
                return

            try:
                result = self._prepare(token)
            except Exception as exc:  # preserve worker failures for drain_ready
                with self._lock:
                    state = self._states.get(key)
                    if (
                        state is None
                        or state.generation != generation
                        or state.pending is not None
                    ):
                        continue
                    state.error = exc
                    state.active = False
                self._notify_key(key)
                return

            with self._lock:
                state = self._states.get(key)
                if self._closed:
                    if state is not None:
                        state.active = False
                    return
                if state is None or state.generation != generation:
                    continue
                if state.pending is not None:
                    # A newer request arrived while this one was preparing.
                    continue
                state.ready = ReadyResult(key, token, result)
                state.active = False
            self._notify_key(key)
            return

    def _notify_key(self, key: Key) -> None:
        if self._notify is not None:
            self._notify(key)

    def drain_ready(self) -> list[ReadyResult[Key, Token, Result]]:
        """Return current ready results, raising any current worker failure.

        Results are removed before returning.  A request arriving concurrently
        is therefore never accidentally drained as an older result.
        """
        with self._lock:
            ready: list[ReadyResult[Key, Token, Result]] = []
            errors: list[Exception] = []
            for _key, state in list(self._states.items()):
                if state.ready is not None:
                    ready.append(state.ready)  # type: ignore[arg-type]
                    state.ready = None
                if state.error is not None:
                    errors.append(state.error)
                    state.error = None
            if errors:
                raise errors[0]
            return ready

    def close(self) -> None:
        """Stop accepting work and join worker threads safely."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for state in self._states.values():
                state.pending = None
                state.ready = None
                state.error = None
        self._executor.shutdown(wait=True)
