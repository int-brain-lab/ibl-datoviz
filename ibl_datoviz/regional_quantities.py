"""Prepared regional scalar quantities using the viewer's anatomy transaction.

The source payload is independent of the active mapping. One regional quantity
can own the anatomy mesh's scalar colors at a time; no additional mesh or data
reader is created here.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from threading import get_ident
from typing import TYPE_CHECKING

import numpy as np

from .payloads import WorldFrame, _array, _provenance, _text
from .presentation import region_presentation, scalar_colors
from .regions import AtlasRegionValues

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, eq=False)
class RegionValues:
    """Prepared scalars on unique signed Allen IDs with explicit reduction weights.

    NaNs retain missing scalar rows. Weights describe the declared aggregation
    population, not anatomical volume or a harmonized scientific cohort. ``units``
    must explicitly say ``dimensionless`` when appropriate.
    """

    allen_region_ids: np.ndarray
    values: np.ndarray
    weights: np.ndarray
    name: str
    units: str
    weight_name: str
    frame: WorldFrame
    provenance: Mapping

    def __post_init__(self):
        """Validate the source description and own immutable array storage."""
        for field in ('name', 'units', 'weight_name'):
            _text(getattr(self, field), field)
        if not isinstance(self.frame, WorldFrame):
            raise ValueError('frame must be a WorldFrame')
        self.frame.require_verified()
        raw_ids = np.asarray(self.allen_region_ids)
        if raw_ids.dtype.kind in 'iu' and raw_ids.size:
            limits = np.iinfo(np.int64)
            if np.any(raw_ids < limits.min) or np.any(raw_ids > limits.max):
                raise ValueError('Allen region IDs must fit signed int64')
        if self.weights is None:
            raise ValueError('regional weights must be explicitly supplied')
        prepared = AtlasRegionValues.from_arrays(
            self.allen_region_ids,
            self.values,
            weights=self.weights,
            value_name=self.name,
            weight_name=self.weight_name,
        )
        for field in ('allen_region_ids', 'values', 'weights'):
            values = getattr(prepared, field)
            object.__setattr__(self, field, _array(values, values.dtype))
        object.__setattr__(self, 'provenance', _provenance(self.provenance))

    def _atlas_values(self):
        return AtlasRegionValues(
            self.allen_region_ids,
            self.values,
            self.weights,
            f'{self.name} [{self.units}]',
            self.weight_name,
        )


@dataclass(frozen=True, eq=False)
class MappedRegionValues:
    """Current mapping's scalar population and separate missing-value coverage.

    ``declared_weights`` includes missing rows; ``finite_weights`` is the
    denominator actually used by the weighted mean. Unmapped source IDs remain
    explicit instead of being mistaken for zero-valued mapped regions.
    """

    mapping: str
    region_ids: np.ndarray
    values: np.ndarray
    declared_weights: np.ndarray
    finite_weights: np.ndarray
    source_counts: np.ndarray
    finite_counts: np.ndarray
    unmapped_source_ids: np.ndarray


def _mapped(payload, catalog, mapping):
    presentation = region_presentation(
        catalog,
        mapping,
        payload._atlas_values(),
        None,
        'sequential',
        1.0,
    )
    mapped = catalog.map_allen_ids(payload.allen_region_ids, mapping)
    groups = {int(key): index for index, key in enumerate(presentation.region_ids)}
    finite_weights = np.zeros(len(groups), dtype=np.float64)
    counts = np.zeros(len(groups), dtype=np.int64)
    finite_counts = np.zeros(len(groups), dtype=np.int64)
    unmapped = []
    for source_id, target_id, value, weight in zip(
        payload.allen_region_ids,
        mapped,
        payload.values,
        payload.weights,
        strict=True,
    ):
        if target_id is None or target_id == 0:
            unmapped.append(source_id)
            continue
        index = groups[int(target_id)]
        counts[index] += 1
        if np.isfinite(value):
            finite_weights[index] += weight
            finite_counts[index] += 1
    if not np.isfinite(presentation.weights).all() or not np.isfinite(finite_weights).all():
        raise ValueError('mapped regional coverage weights overflow float64')
    arrays = (
        presentation.region_ids,
        presentation.values,
        presentation.weights,
        finite_weights,
        counts,
        finite_counts,
        np.asarray(unmapped, dtype=np.int64),
    )
    return MappedRegionValues(mapping, *(_array(value, value.dtype) for value in arrays))


class RegionalQuantityHandle:
    """Owned scalar presentation of one immutable regional payload."""

    def __init__(self, registry, payload, name):
        self._registry, self._payload, self._name = registry, payload, name
        self._closed = False
        self._visible = False
        self._cmap, self._limits = 'sequential', None
        self._opacity: float | None = None

    @property
    def payload(self):
        """Complete original signed region rows, unaffected by mapping changes."""
        return self._payload

    @property
    def name(self):
        """Display label independent of scientific region identity."""
        return self._name

    @property
    def visible(self):
        """Whether this quantity currently supplies anatomy scalar colors."""
        return self._visible

    @property
    def cmap(self):
        """The existing supported sequential or diverging color scheme."""
        return self._cmap

    @property
    def limits(self):
        """Explicit scalar limits, or None for automatic finite-value limits."""
        return self._limits

    @property
    def opacity(self) -> float | None:
        """Regional scalar alpha override, or None for the default palette alpha."""
        return self._opacity

    def set_opacity(self, opacity: float | None) -> None:
        """Set scalar alpha in [0, 1]; None restores the default palette alpha.

        Hidden quantities retain the setting without changing anatomy. A native
        update must succeed before the handle commits the new opacity.
        """
        self._check()
        if opacity is not None:
            if (
                isinstance(opacity, (bool, np.bool_))
                or not isinstance(opacity, Real)
                or not np.isfinite(opacity)
                or not 0 <= opacity <= 1
            ):
                raise ValueError('regional opacity must be None or a finite number in [0, 1]')
            opacity = float(opacity)
        if self._visible:
            self._registry._apply(self, cmap=self._cmap, limits=self._limits, opacity=opacity)
        self._opacity = opacity

    def _check(self, *, read_only=False):
        if self._closed:
            raise RuntimeError('regional quantity is removed or viewer is closed')
        if read_only:
            viewer = self._registry.viewer
            if self._registry._closed or getattr(viewer, '_closed', False):
                raise RuntimeError('viewer is closed')
            if get_ident() != getattr(viewer, '_owner_thread', get_ident()):
                raise RuntimeError('viewer operations require its owning thread')
        else:
            self._registry._check()

    def mapped(self, mapping=None):
        """Return weighted means and coverage without modifying source populations."""
        self._check(read_only=True)
        viewer = self._registry.viewer
        selected_mapping = viewer.mapping if mapping is None else mapping
        return _mapped(self.payload, viewer.catalog, selected_mapping)

    def color_by(self, field, *, cmap='sequential', limits=None):
        """Color by the prepared value using an explicitly supported scheme."""
        self._check()
        if field != 'value':
            raise ValueError("regional quantities support color_by('value') only")
        if cmap not in ('sequential', 'diverging'):
            raise ValueError('regional cmap must be sequential or diverging')
        scalar_colors(self.payload.values, limits, cmap)
        canonical_limits = None if limits is None else tuple(float(x) for x in limits)
        if self._visible:
            self._registry._apply(self, cmap=cmap, limits=canonical_limits, opacity=self._opacity)
        self._cmap, self._limits = cmap, canonical_limits

    def set_visible(self, visible):
        """Restore previous anatomy scalar settings while hidden."""
        self._check()
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('regional visibility must be boolean')
        visible = bool(visible)
        if visible == self._visible:
            return
        if visible:
            self._registry._apply(
                self, cmap=self._cmap, limits=self._limits, opacity=self._opacity
            )
        else:
            self._registry._restore_previous()
        self._visible = visible

    def remove(self):
        """Restore prior anatomy colors and release exclusive ownership."""
        self._check()
        if self._visible:
            self._registry._restore_previous()
        self._visible = False
        self._closed = True
        self._registry._handle = None


class RegionQuantityRegistry:
    """Enforce the one-active-quantity contract of one anatomy mesh."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._handle = None
        self._previous = None
        self._closed = False

    @property
    def handle(self):
        """The attached quantity, including an attached hidden quantity."""
        return self._handle

    def _check(self):
        if self._closed:
            raise RuntimeError('regional quantity registry is closed')
        self.viewer.selection._check_mutation()

    def add(self, payload, *, name='', mapping_reduction):
        """Attach one prepared scalar field with an explicit reduction decision."""
        self._check()
        if self._handle is not None:
            raise ValueError('an anatomy regional quantity is already attached; remove it first')
        if not isinstance(payload, RegionValues):
            raise TypeError('payload must be RegionValues')
        if mapping_reduction != 'weighted_mean':
            raise ValueError('regional mapping_reduction must be weighted_mean')
        viewer = self.viewer
        if viewer.catalog is None:
            raise ValueError('regional quantity requires an atlas region catalog')
        viewer._validate_layer_frame(payload.frame)
        display_name = payload.name if name == '' else _text(name, 'name')
        _mapped(payload, viewer.catalog, viewer.mapping)
        previous = (
            viewer.region_data,
            viewer._region_value_range,
            viewer._region_color_scheme,
            viewer._region_opacity,
        )
        handle = RegionalQuantityHandle(self, payload, display_name)
        self._apply(handle, cmap=handle.cmap, limits=handle.limits, opacity=handle.opacity)
        self._previous = previous
        self._handle = handle
        handle._visible = True
        return handle

    def _apply(self, handle, *, cmap, limits, opacity):
        self.viewer._set_owned_region_data(
            handle.payload._atlas_values(),
            value_range=limits,
            color_scheme=cmap,
            opacity=opacity,
            mapping_reduction='weighted_mean',
        )

    def _restore_previous(self):
        data, limits, cmap, opacity = self._previous
        self.viewer._set_owned_region_data(
            data,
            value_range=limits,
            color_scheme=cmap,
            opacity=opacity,
            mapping_reduction='weighted_mean',
        )

    def _close(self):
        if self._handle is not None:
            self._handle._closed = True
            self._handle._visible = False
            self._handle = None
        self._previous = None
        self._closed = True
