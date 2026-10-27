#!/usr/bin/env python3
"""Inspect real prepared BWM site values, missingness and retained scalar tables."""

from __future__ import annotations

import argparse

import numpy as np

from examples.bwm_probe import FIXTURE, _load_fixture
from examples.scientific_common import add_arguments, finish, prepare_viewer
from examples.scientific_scene_review import firing_rate_range
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasViewer, Points, SourceKey, SourceObservationKey


class ScalarReview(AtlasViewer):
    """A small offline client over the public layer, table and selection API."""

    def configure(self, sites, provenance):
        """Keep the fixture's co-located site IDs and existing prepared values."""
        self.review_sites = sites
        self.value_range = firing_rate_range(sites)
        source = SourceKey(
            'IBL',
            provenance['dataset']['name'],
            provenance['dataset']['version'],
            provenance['artifact']['sha256'],
        )
        keys = tuple(
            SourceObservationKey(
                source, provenance['insertion']['pid'], 'co-located-channel-groups', int(site)
            )
            for site in sites.site_ids
        )
        metadata = {
            **provenance,
            'position_meaning': 'Prepared co-located BWM channel groups; source ML/AP/DV (um).',
            'scalar_description': provenance['derivation']['value'],
            'scalar_missing_meaning': 'Missing FR: no good unit assigned to this channel group.',
        }
        self.site_layer = self.add_points(
            Points(
                tuple(map(int, sites.site_ids)),
                sites.positions_um,
                self.frame,
                metadata,
                keys,
                allen_region_ids=sites.allen_region_ids,
            ),
            name='BWM channel groups',
        )
        self.site_layer.set_size_px(12)
        self.encode_values()
        self.tables.show(self.site_layer)

    def encode_values(self):
        """Use explicit finite-site 5th/95th percentile color limits; retain raw values."""
        layer = self.site_layer
        layer.color_by(
            self.review_sites.values,
            name='Mean good-unit firing rate',
            units='Hz',
            cmap='viridis',
            limits=self.value_range,
            missing_color='#808080',
            observation_refs=layer.payload.observation_keys,
        )

    def _draw_viewport_toolbar_gui(self, gui):
        super()._draw_viewport_toolbar_gui(gui)
        layer = getattr(self, 'site_layer', None)
        if layer is None:
            return
        dvz = self.dvz
        label = b'Use uniform color' if layer.scalar_encoding is not None else b'Restore FR colors'
        if dvz.dvz_gui_button(gui, label):
            if layer.scalar_encoding is not None:
                layer.set_color('#40dcfa')
            else:
                self.encode_values()
        for finite, label in ((True, b'Select measured site'), (False, b'Select missing FR')):
            dvz.dvz_gui_same_line(gui, 0, 8 * self.ui_scale)
            if dvz.dvz_gui_button(gui, label):
                rows = np.flatnonzero(np.isfinite(self.review_sites.values) == finite)
                self.selection.set_observations((layer.refs[int(rows[0])],) if len(rows) else ())


def main():
    """Open verified anatomy plus the hash-checked, existing BWM fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument('volume_root')
    args = parser.parse_args()
    sites, provenance = _load_fixture(FIXTURE)
    options = prepare_viewer(args)
    options.update(
        layout='linked',
        volumes=open_volume_pack(args.volume_root).load_volumes(),
        render_volume=False,
    )
    with ScalarReview(**options) as app:
        app.configure(sites, provenance)
        report = {
            'fixture_sha256': provenance['artifact']['sha256'],
            'sites': len(sites.site_ids),
            'finite_values': int(np.isfinite(sites.values).sum()),
            'missing_values': int(np.isnan(sites.values).sum()),
            'color_limits_hz': app.value_range,
            'color_limits_policy': 'finite-site 5th/95th percentiles; source values unchanged',
        }
        finish(app, args, report, 'BWM scalar values review')


if __name__ == '__main__':
    main()
