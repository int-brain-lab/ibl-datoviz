"""Latest-wins scheduling primitives for exact atlas slices.

This module deliberately has no Datoviz dependencies.  A GUI owner creates an
immutable :class:`SliceRequest` whenever its cursor or slice presentation
state changes, submits it, and applies only the corresponding
:class:`PreparedSlice` on the owner thread.  Revisions are monotonic per axis;
an old worker result can therefore never replace a newer slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Generic, Literal, TypeVar

from .latest_wins import LatestWinsExecutor

if TYPE_CHECKING:
    from collections.abc import Callable

Axis = Literal['ap', 'ml', 'dv']
Payload = TypeVar('Payload', bound=object)


@dataclass(frozen=True, slots=True)
class SliceRequest:
    """Complete identity of one exact-resolution slice preparation.

    ``revision`` is assigned by the UI state owner and must increase for each
    new request on an axis. ``source_id`` identifies the immutable grid/asset
    contract so an alternate-resolution result cannot accidentally publish
    into the wrong visual. Presentation values are intentionally represented
    as immutable scalars/tuples rather than a mutable viewer object.
    """

    axis: Axis
    index: int
    revision: int
    source_id: str = ''
    mapping: str = 'allen'
    annotation_opacity: float = 1.0
    anatomy_visible: bool = True
    annotation_visible: bool = True
    selected_region_ids: tuple[int, ...] = ()
    selection_dim_factor: float = 1.0

    def __post_init__(self) -> None:
        """Validate the immutable request at its construction boundary."""
        if self.axis not in ('ap', 'ml', 'dv'):
            raise ValueError(f'unknown slice axis: {self.axis!r}')
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise TypeError('slice index must be an integer')
        if self.revision < 0:
            raise ValueError('slice revision must be non-negative')
        if not isinstance(self.selected_region_ids, tuple):
            raise TypeError('selected_region_ids must be an immutable tuple')


@dataclass(frozen=True, slots=True)
class PreparedSlice(Generic[Payload]):
    """A worker result paired with the request that produced it."""

    request: SliceRequest
    payload: Payload


class SliceScheduler(Generic[Payload]):
    """Prepare at most the newest request independently for each axis.

    ``prepare`` must be renderer-free.  Its payload is returned to the caller
    by :meth:`drain_ready`, which is the only point where the owner should
    mutate Datoviz resources.  Submitting a revision older than or equal to
    the latest revision for that axis is a no-op and returns ``False``.
    """

    def __init__(
        self,
        prepare: Callable[[SliceRequest], Payload],
        *,
        notify: Callable[[Axis], object] | None = None,
        max_workers: int = 3,
    ) -> None:
        self._prepare = prepare
        self._lock = RLock()
        self._latest_revision: dict[Axis, int] = {}
        self._executor = LatestWinsExecutor[Axis, SliceRequest, Payload](
            prepare,
            notify=notify,
            max_workers=max_workers,
        )

    def submit(self, request: SliceRequest) -> bool:
        """Submit ``request`` if it advances that axis; return acceptance."""
        with self._lock:
            latest = self._latest_revision.get(request.axis, -1)
            if request.revision <= latest:
                return False
            self._latest_revision[request.axis] = request.revision
            self._executor.request(request.axis, request)
            return True

    def latest_revision(self, axis: Axis) -> int | None:
        """Return the newest submitted revision for ``axis``."""
        with self._lock:
            return self._latest_revision.get(axis)

    def drain_ready(self) -> list[PreparedSlice[Payload]]:
        """Return current results, excluding anything no longer current."""
        ready = self._executor.drain_ready()
        with self._lock:
            return [
                PreparedSlice(item.token, item.result)
                for item in ready
                if item.token.revision == self._latest_revision.get(item.key)
            ]

    def close(self) -> None:
        """Stop workers and reject subsequent submissions."""
        self._executor.close()
