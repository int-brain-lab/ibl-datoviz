"""Offscreen opaque insertion pixels and viewer wrapper lifetime checks."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer, InsertionCollectionVisual
from tests.test_atlas import FIXTURE, FakeDatoviz


@pytest.fixture
def native_scene():
    scene = app = None
    components = []
    dvz = None
    try:
        try:
            import datoviz as dvz  # noqa: PLC0415 - native runtime may be absent on CI.

            scene = dvz.dvz_scene()
            assert scene
            figure = dvz.dvz_figure(scene, 200, 160, 0)
            assert figure
            panel = dvz.dvz_panel_full(figure)
            assert panel
            assert dvz.dvz_panel_set_background_color(panel, dvz.DvzColor(255, 255, 255, 255)) == 0
            app = dvz.dvz_app(scene)
            if not app:
                pytest.skip('Datoviz native runtime or GPU context is unavailable')
            view = dvz.dvz_view_offscreen(app, figure, 200, 160)
            assert view
        except RuntimeError as error:
            if 'Unable to load libdatoviz' in str(error):
                pytest.skip('Datoviz native runtime or GPU context is unavailable')
            raise

        def capture():
            assert dvz.dvz_view_render_once(view) == 0
            pixels = np.array(dvz.dvz_view_capture_rgba(view), copy=True)
            assert pixels.shape == (160, 200, 4) and pixels.dtype == np.uint8
            return pixels

        yield SimpleNamespace(
            dvz=dvz,
            scene=scene,
            panel=panel,
            capture=capture,
            components=components,
        )
    finally:
        for component in reversed(components):
            component.close()
        if app:
            dvz.dvz_app_destroy(app)
        if scene:
            dvz.dvz_scene_destroy(scene)


def colored_path(pixels, rgb):
    return np.all(pixels[..., :3] == np.asarray(rgb, np.uint8), axis=2)


def test_native_paths_render_independently_replace_remove_and_leave_scene_alive(
    native_scene,
):
    context = native_scene
    paths = InsertionCollectionVisual(context.dvz, context.scene, context.panel)
    context.components.append(paths)

    left = np.array(
        [[-0.82, -0.55, 0], [-0.55, -0.25, 0], [-0.25, -0.55, 0]],
        dtype=np.float32,
    )
    right = np.array(
        [[0.25, 0.55, 0], [0.55, 0.25, 0], [0.82, 0.55, 0]],
        dtype=np.float32,
    )
    baseline = context.capture()
    paths.set_insertion('left', left, color=(230, 30, 25), width_px=9)
    left_visual = paths._insertions['left'].visual
    paths.set_insertion(17, right, color=(20, 60, 230), width_px=9)
    right_visual = paths._insertions[17].visual
    both = context.capture()
    assert paths.ids == ('left', 17)
    assert left_visual != right_visual
    assert np.count_nonzero(colored_path(both, (230, 30, 25))) > 20
    assert np.count_nonzero(colored_path(both, (20, 60, 230))) > 20

    # Recoloring one path leaves the other path's exact pixels untouched.
    paths.set_color('left', (20, 190, 40, 255))
    recolored_left = context.capture()
    np.testing.assert_array_equal(
        colored_path(recolored_left, (20, 60, 230)),
        colored_path(both, (20, 60, 230)),
    )
    assert np.count_nonzero(colored_path(recolored_left, (20, 190, 40))) > 20

    # A different vertex count and geometry replace the second native path in place.
    moved_right = np.array(
        [[0.12, 0.65, 0], [0.4, 0.72, 0], [0.65, 0.64, 0], [0.88, 0.70, 0]],
        dtype=np.float32,
    )
    paths.set_insertion(17, moved_right, color=(220, 140, 15), width_px=7)
    replaced = context.capture()
    assert paths._insertions[17].visual == right_visual
    assert np.count_nonzero(colored_path(replaced, (20, 60, 230))) == 0
    assert np.count_nonzero(colored_path(replaced, (220, 140, 15))) > 20
    assert np.count_nonzero(colored_path(replaced, (20, 190, 40))) > 20

    paths.set_visible('left', False)
    second_only = context.capture()
    assert np.count_nonzero(colored_path(second_only, (20, 190, 40))) == 0
    assert np.count_nonzero(colored_path(second_only, (220, 140, 15))) > 20
    paths.set_visible('left', True)
    paths.remove('left')
    np.testing.assert_array_equal(context.capture(), second_only)
    paths.remove(17)
    np.testing.assert_array_equal(context.capture(), baseline)

    # Closing the component does not own or destroy the caller's scene/panel/app.
    paths.set_insertion('lifetime', left, color=(160, 40, 180), width_px=8)
    paths.close()
    paths.close()
    np.testing.assert_array_equal(context.capture(), baseline)
    survivor = InsertionCollectionVisual(context.dvz, context.scene, context.panel)
    context.components.append(survivor)
    survivor.set_insertion('scene-still-live', right, color=(20, 60, 230), width_px=8)
    assert np.count_nonzero(colored_path(context.capture(), (20, 60, 230))) > 20
    survivor.close()


@pytest.mark.parametrize(('angle', 'width_px'), [(0.0, 7.0), (0.9, 3.0)])
def test_native_repeated_channel_positions_keep_a_bounded_visible_path(
    native_scene, angle, width_px
):
    """Coincident channel rows must neither create spikes nor disappear on upload."""
    context = native_scene
    paths = InsertionCollectionVisual(context.dvz, context.scene, context.panel)
    context.components.append(paths)
    xy = np.array([[0.7, 0.04], [0.3, 0.02], [-0.1, 0], [-0.6, -0.025]])
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    points = np.column_stack((xy @ rotation.T, np.zeros(len(xy)))).astype(np.float32)
    repeated = np.repeat(points, 2, axis=0)
    paths.set_insertion('paired-channels', repeated, color=(230, 30, 25), width_px=width_px)
    pixels = context.capture()
    mask = colored_path(pixels, (230, 30, 25))
    y, x = np.where(mask)
    assert len(x) > 50  # Empty/thin output is not an acceptable way to remove spikes.
    samples = np.column_stack((x + 0.5, y + 0.5))
    projected = np.column_stack(((points[:, 0] + 1) * 100, (1 - points[:, 1]) * 80))
    starts, edges = projected[:-1], np.diff(projected, axis=0)
    relative = samples[:, None, :] - starts
    t = np.clip((relative * edges).sum(axis=2) / (edges * edges).sum(axis=1), 0, 1)
    distances = np.linalg.norm(relative - t[..., None] * edges, axis=2).min(axis=1)
    assert distances.max() <= width_px / 2 + 2  # Pixel centres and antialias margin.
    np.testing.assert_array_equal(paths.get_data('paired-channels').positions_um, repeated)
    assert not paths.get_data('paired-channels').positions_um.flags.writeable

    paths.set_insertion('paired-channels', points, color=(230, 30, 25), width_px=width_px)
    reference = colored_path(context.capture(), (230, 30, 25))
    # Repeated observations preserve the displayed centreline, including its real ends.
    assert np.count_nonzero(mask & reference) >= 0.95 * np.count_nonzero(reference)


class InsertionsFake(FakeDatoviz):
    """Viewer fake tracking only path visuals owned by insertions."""

    def dvz_visual_set_depth_test(self, visual, enabled):
        self.calls.append(('depth_test', visual.name, bool(enabled)))
        return 0

    def __init__(self):
        super().__init__()
        self.destroyed_visuals = []

    def dvz_visual_destroy(self, visual):
        self.destroyed_visuals.append(visual)
        self.calls.append(('visual_destroy', visual.name))


def test_atlas_viewer_insertion_wrappers_keep_ids_separate_from_probe():
    mesh = AtlasMesh.from_pack(FIXTURE)
    fake = InsertionsFake()
    viewer = AtlasViewer(mesh, datoviz=fake)
    viewer.set_insertion('probe-A', [[0, 0, 0], [100, 100, 100]])
    viewer.set_insertion(22, [[50, 0, 0], [100, 50, 0]], color=(20, 30, 40))
    viewer.set_insertion_color('probe-A', (60, 70, 80))
    viewer.set_insertion_width(22, 6)
    viewer.set_insertion_visible('probe-A', False)
    assert viewer.insertion_ids == ('probe-A', 22)
    viewer.remove_insertion(22)
    assert viewer.insertion_ids == ('probe-A',)
    insertion_visual = viewer._insertions._insertions['probe-A'].visual
    viewer.close()
    assert len(fake.destroyed_visuals) == 2  # Removed path plus viewer-owned survivor.
    assert fake.destroyed_visuals[-1] is insertion_visual
    assert ('destroy_scene',) in fake.calls
    assert fake.calls.index(('visual_destroy', 'path')) < fake.calls.index(('destroy_scene',))
