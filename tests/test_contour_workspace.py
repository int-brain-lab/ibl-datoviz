"""Optional exact geometry shares one viewer and accepted displayed section identity."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasCursor, AtlasMesh, AtlasViewer
from ibl_datoviz.contour_source import ContourSection
from ibl_datoviz.navigator import oriented_slice
from ibl_datoviz.slice_preparation import prepare_slice_layers
from tests.test_latest_wins import wait_until
from tests.test_volume_free_navigator import MESH, VOLUME


class ExactSource:
    """Small complete source with a numerical contour for every exact label cell."""

    def __init__(self):
        self.source = open_volume_pack(VOLUME).load_volumes()

    def __getattr__(self, name):
        return getattr(self.source, name)

    def contour_slice(self, axis, index):
        section = self.source.slice('annotation', axis, index)
        labels = oriented_slice(section.values, section.array_axes, axis, grid=self.grid)
        height, width = labels.shape
        paths = []
        for y, x in np.argwhere(labels != 0):
            row = self.source.region_for_source_index(int(labels[y, x]))
            if row.atlas_id == 0:
                continue
            component = SimpleNamespace(
                outer=np.array([[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]]), holes=()
            )
            paths.append(
                SimpleNamespace(atlas_ids={'allen': row.atlas_id}, components=(component,))
            )
        matrix = np.diag([1 / width, 1 / height, 1])
        return ContourSection(tuple(paths), tuple(matrix.reshape(-1)))


@pytest.fixture
def viewer():
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(MESH),
        layout='linked',
        slice_source=ExactSource(),
        render_volume=False,
        slice_renderer='contours',
        enable_hover=True,
        width=640,
        height=480,
    ) as app:
        yield app


def test_contour_source_is_explicit_and_validated_before_native_creation():
    source = open_volume_pack(VOLUME).load_volumes()
    with pytest.raises(ValueError, match='exact registered'):
        AtlasViewer(
            atlas=AtlasMesh.from_pack(MESH),
            layout='linked',
            volumes=source,
            slice_renderer='contours',
        )


def test_contours_owned_under_same_viewer_and_original_signed_mapping(viewer, tmp_path):
    app = viewer
    assert set(app._accepted_contours) == {'ap', 'ml', 'dv'}
    app.selection.set_regions((-315,), mapping='allen')
    app.render_offscreen(tmp_path / 'contours.png')
    assert (tmp_path / 'contours.png').is_file()
    for axis, (request, payload) in app._accepted_contours.items():
        assert request.renderer == 'contours' and request.mapping == app.mapping
        assert payload.contours.mapping == request.mapping
        assert payload.contours.components
        assert len(app._contour_visuals[axis]._buffers) == 2
    app.set_mapping('cosmos')

    def accepted():
        app._process_gui_frame()
        return all(r.mapping == 'cosmos' for r, _ in app._accepted_contours.values())

    wait_until(accepted)


def test_hover_and_click_use_displayed_section_while_new_request_is_pending(viewer):
    app = viewer
    axis = 'ap'
    old_request, payload = app._accepted_contours[axis]
    component = payload.contours.components[0]
    svg = component.outer.mean(axis=0)
    matrix = np.asarray(payload.svg_to_fraction).reshape(3, 3)
    fraction = svg @ matrix[:2, :2].T + matrix[:2, 2]
    quad, _ = app._slice_quad(axis)
    point = quad[0, :2] + fraction * (quad[3, :2] - quad[0, :2])
    app.cursor = AtlasCursor(1 - old_request.index, 2, 1)
    assert app._cursor_at_slice_data(axis, *point).ap == old_request.index
    assert app._contour_region_at(axis, *point) == component.atlas_id
    app._set_slice_hover(axis, *point)
    assert app._hovered_region_ids == (component.atlas_id,)
    app.mapping = 'cosmos'
    assert app._cursor_at_slice_data(axis, *point) is None
    assert app._contour_region_at(axis, *point) is None
    app.mapping = 'allen'


def test_stale_request_does_not_replace_geometry_or_identity(viewer):
    app = viewer
    request, payload = app._accepted_contours['ap']
    app._slice_revisions['ap'] += 1
    active = app._contour_visuals['ap']._active
    app._upload_slice_payload(request, payload)
    assert app._contour_visuals['ap']._active == active
    assert app._accepted_contours['ap'][0] == request


def test_zoom_remaps_accepted_geometry_without_new_slice_io(viewer, monkeypatch):
    app = viewer
    before = app._accepted_contours.copy()
    monkeypatch.setattr(
        app.slice_source, 'contour_slice', lambda *_: pytest.fail('zoom read source')
    )
    app._slice_zoom['ap'] = 2
    app._update_slice_geometry('ap')
    assert app._accepted_contours == before


def test_prepared_contours_are_captured_and_do_not_mutate_with_owner(viewer):
    request = viewer._slice_request('ap')
    payload = prepare_slice_layers(viewer.slice_composer, request)
    assert payload.contours.mapping == request.mapping
    assert isinstance(payload.svg_to_fraction, tuple)
    assert payload.boundary_starts.flags.writeable is False


@pytest.mark.parametrize('offset', [0.1, 0.5, 0.9])
def test_exact_cell_interior_roundtrips_to_the_same_cursor_and_identity(viewer, offset):
    app = viewer
    for axis, (request, _payload) in app._accepted_contours.items():
        x_axis, y_axis = {'ap': ('ml', 'dv'), 'ml': ('ap', 'dv'), 'dv': ('ml', 'ap')}[axis]
        grid = app.slice_source.grid
        corners, _ = app._slice_quad(axis)
        for x in range(grid.shape[grid.array_axes.index(x_axis)]):
            for y in range(grid.shape[grid.array_axes.index(y_axis)]):
                fraction = np.array(
                    [app._slice_fraction(x_axis, x), app._slice_fraction(y_axis, y)]
                )
                fraction += (offset - 0.5) / np.array(
                    [
                        grid.shape[grid.array_axes.index(x_axis)],
                        grid.shape[grid.array_axes.index(y_axis)],
                    ]
                )
                point = corners[0, :2] + fraction * (corners[3, :2] - corners[0, :2])
                cursor = app._cursor_at_slice_data(axis, *point)
                expected = dict(zip(('ap', 'ml', 'dv'), cursor.as_index(), strict=True))
                assert expected[axis] == request.index
                assert expected[x_axis] == x and expected[y_axis] == y
                row = cursor.region(app.slice_source, app.mapping)
                region_id = None if row is None or row.atlas_id == 0 else row.atlas_id
                assert app._contour_region_at(axis, *point) == region_id


def test_unknown_pending_geometry_does_not_clear_existing_selection(viewer, monkeypatch):
    app = viewer
    app.selection.set_regions((-315,), mapping='allen')
    old = app.cursor.as_index()
    next_cursor = AtlasCursor(*(0 if value else 1 for value in old))
    # The async path changes requested state before any new plane is accepted.
    monkeypatch.setattr(app, '_refresh_slices', lambda *_: None)
    app.set_cursor(next_cursor, select_region=True)
    assert app._contour_region_query() == (False, None)
    assert app.selection.regions == (('allen', -315),)
