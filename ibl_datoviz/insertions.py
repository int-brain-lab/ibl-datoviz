"""Owned insertion trajectory data and caller-scene visual collections."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

from .component import ComponentVisual, owned, rgba_array

_UNSET = object()


@dataclass(frozen=True)
class InsertionTrajectory:
    """Immutable opaque trajectory coordinates and scalar path style."""

    positions_um: np.ndarray
    color: Sequence[int] = (255, 205, 72, 255)
    width_px: float = 4.0

    def __post_init__(self):
        """Validate, copy, and freeze the trajectory payload."""
        positions = owned(self.positions_um, np.float32)
        if (
            positions.ndim != 2
            or positions.shape[1] != 3
            or len(positions) < 2
            or not np.isfinite(positions).all()
        ):
            raise ValueError('insertion positions must be finite with shape (n>=2, 3)')
        color = rgba_array(np.asarray(self.color), ())
        if color[3] != 255:
            raise ValueError('insertion paths require opaque alpha; transparency is unsupported')
        raw_width = np.asarray(self.width_px)
        if raw_width.shape != () or raw_width.dtype.kind not in 'iuf':
            raise ValueError('insertion width must be a finite positive number')
        width = float(raw_width)
        stored_width = np.float32(width)
        if (
            not np.isfinite(width)
            or width <= 0
            or not np.isfinite(stored_width)
            or stored_width <= 0
        ):
            raise ValueError('insertion width must be finite and positive')
        object.__setattr__(self, 'positions_um', positions)
        object.__setattr__(self, 'color', color)
        object.__setattr__(self, 'width_px', float(stored_width))

    @classmethod
    def from_arrays(
        cls,
        positions_um,
        *,
        color=(255, 205, 72, 255),
        width_px=4.0,
    ) -> InsertionTrajectory:
        """Copy and validate an opaque path payload."""
        return cls(positions_um, color, width_px)


@dataclass
class _Insertion:
    data: InsertionTrajectory
    visual: object
    display_positions: np.ndarray
    visible: bool = True


def _identity(value):
    if isinstance(value, str):
        if not value:
            raise ValueError('insertion identity must be a non-empty string or positive integer')
        return value
    if isinstance(value, Integral) and not isinstance(value, (bool, np.bool_)) and value > 0:
        return int(value)
    raise ValueError('insertion identity must be a non-empty string or positive integer')


class InsertionCollectionVisual(ComponentVisual):
    """Manage multiple independent opaque paths in a borrowed scene and panel.

    Each identity owns one native path. The collection borrows the scene and
    panel and must be closed before their caller destroys the scene.
    """

    def __init__(self, dvz, scene, panel, *, transform=None):
        super().__init__(dvz, scene, panel, transform)
        self._insertions: dict[str | int, _Insertion] = {}

    @property
    def ids(self) -> tuple[str | int, ...]:
        """Insertion identities in creation order."""
        return tuple(self._insertions)

    def get_data(self, insertion_id) -> InsertionTrajectory:
        """Return immutable trajectory data for one identity."""
        self._require_open()
        key = _identity(insertion_id)
        try:
            return self._insertions[key].data
        except KeyError as exc:
            raise KeyError(f'unknown insertion identity: {key!r}') from exc

    @staticmethod
    def _attributes(data, display_positions):
        count = len(data.positions_um)
        colors = np.tile(data.color, (count, 1))
        widths = np.full(count, data.width_px, dtype=np.float32)
        colors.setflags(write=False)
        widths.setflags(write=False)
        return {
            'position': display_positions,
            'color': colors,
            'stroke_width_px': widths,
        }

    def _upload(self, visual, data, display_positions, context='insertion upload'):
        self._check(
            self.dvz.dvz_visual_set_data_many(visual, self._attributes(data, display_positions)),
            context,
        )

    def _new_visual(self, data, display_positions):
        visual = self._required(self.dvz.dvz_path(self.scene, 0), 'dvz_path')
        try:
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(visual, self.dvz.DVZ_ALPHA_OPAQUE),
                'insertion opaque alpha',
            )
            self._check(self.dvz.dvz_visual_set_depth_test(visual, True), 'insertion depth test')
            self._check(
                self.dvz.dvz_path_set_caps(
                    visual,
                    self.dvz.DVZ_SEGMENT_CAP_ROUND,
                    self.dvz.DVZ_SEGMENT_CAP_ROUND,
                ),
                'insertion caps',
            )
            self._check(
                self.dvz.dvz_path_set_join(visual, self.dvz.DVZ_PATH_JOIN_ROUND, 4.0),
                'insertion join',
            )
            self._upload(visual, data, display_positions)
            self._check(self.dvz.dvz_visual_set_visible(visual, True), 'insertion visibility')
            self._check(
                self.dvz.dvz_panel_add_visual(self.panel, visual, None),
                'insertion attach',
            )
        except Exception:
            self.dvz.dvz_visual_destroy(visual)
            raise
        return visual

    def set_insertion(
        self,
        insertion_id,
        positions_um,
        *,
        color=(255, 205, 72, 255),
        width_px=4.0,
    ):
        """Create or replace one identified opaque path transactionally."""
        self._require_open()
        key = _identity(insertion_id)
        data = InsertionTrajectory.from_arrays(positions_um, color=color, width_px=width_px)
        display_positions = self._positions(data.positions_um)
        current = self._insertions.get(key)
        if current is None:
            visual = self._new_visual(data, display_positions)
            self._insertions[key] = _Insertion(data, visual, display_positions)
            return

        try:
            self._upload(current.visual, data, display_positions)
        except Exception as error:
            try:
                self._upload(
                    current.visual,
                    current.data,
                    current.display_positions,
                    'insertion rollback',
                )
            except Exception as rollback_error:
                self.dvz.dvz_visual_destroy(current.visual)
                del self._insertions[key]
                raise RuntimeError('insertion rollback failed; visual removed') from rollback_error
            raise error
        current.data = data
        current.display_positions = display_positions

    def _replace_attribute(self, key, *, color=_UNSET, width_px=_UNSET):
        self._require_open()
        insertion_id = _identity(key)
        try:
            current = self._insertions[insertion_id]
        except KeyError as exc:
            raise KeyError(f'unknown insertion identity: {insertion_id!r}') from exc
        data = InsertionTrajectory.from_arrays(
            current.data.positions_um,
            color=current.data.color if color is _UNSET else color,
            width_px=current.data.width_px if width_px is _UNSET else width_px,
        )
        attribute = 'color' if color is not _UNSET else 'stroke_width_px'
        new_value = (
            np.tile(data.color, (len(data.positions_um), 1))
            if color is not _UNSET
            else np.full(len(data.positions_um), data.width_px, dtype=np.float32)
        )
        new_value.setflags(write=False)
        old_value = (
            np.tile(current.data.color, (len(current.data.positions_um), 1))
            if color is not _UNSET
            else np.full(len(current.data.positions_um), current.data.width_px, dtype=np.float32)
        )
        old_value.setflags(write=False)
        try:
            self._check(
                self.dvz.dvz_visual_set_data(current.visual, attribute, new_value),
                f'insertion {attribute}',
            )
        except Exception as error:
            try:
                self._check(
                    self.dvz.dvz_visual_set_data(current.visual, attribute, old_value),
                    f'insertion {attribute} rollback',
                )
            except Exception as rollback_error:
                self.dvz.dvz_visual_destroy(current.visual)
                del self._insertions[insertion_id]
                raise RuntimeError(
                    'insertion style rollback failed; visual removed'
                ) from rollback_error
            raise error
        current.data = data

    def set_color(self, insertion_id, color):
        """Set an insertion's uniform opaque RGB/RGBA color."""
        self._replace_attribute(insertion_id, color=color)

    def set_width(self, insertion_id, width_px):
        """Set an insertion's uniform positive pixel width."""
        self._replace_attribute(insertion_id, width_px=width_px)

    def set_visible(self, insertion_id, visible):
        """Set authored visibility for one insertion."""
        self._require_open()
        key = _identity(insertion_id)
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('visible must be a boolean')
        try:
            item = self._insertions[key]
        except KeyError as exc:
            raise KeyError(f'unknown insertion identity: {key!r}') from exc
        self._check(
            self.dvz.dvz_visual_set_visible(item.visual, bool(visible)),
            'insertion visibility',
        )
        item.visible = bool(visible)

    def remove(self, insertion_id):
        """Destroy one path; removing an absent identity is a no-op."""
        self._require_open()
        key = _identity(insertion_id)
        item = self._insertions.get(key)
        if item is None:
            return False
        self.dvz.dvz_visual_destroy(item.visual)
        del self._insertions[key]
        return True

    def clear(self):
        """Remove every owned path while keeping the collection open."""
        self._require_open()
        for key in tuple(self._insertions):
            self.remove(key)

    def close(self):
        """Destroy owned paths idempotently without destroying borrowed resources."""
        if self._closed:
            return
        errors = []
        for item in tuple(self._insertions.values()):
            try:
                self.dvz.dvz_visual_destroy(item.visual)
            except Exception as error:  # attempt cleanup of every owned path
                errors.append(error)
        self._insertions.clear()
        self._closed = True
        if errors:
            raise RuntimeError('failed to destroy one or more insertion visuals') from errors[0]
