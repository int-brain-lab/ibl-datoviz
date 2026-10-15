"""Approved scientific API: two IBL recordings using the existing shared data seam.

Callable example with the optional shared IBL reader installed. The caller supplies
an existing workspace, verified atlas assets, and reviewed source coordinate-frame evidence.
No discovery or downloads occur.
"""

from ibl_ai_agent.access import open_workspace
from ibl_datoviz import AtlasViewer
from ibl_datoviz.ibl import BwmSource, prepare_bwm_recording


def review_ibl_recordings(
    workspace_root,
    atlas_assets,
    bwm_frame,
    pid_a,
    pid_b,
    cluster_id,
    *,
    anatomical_context=(),
):
    """Review source identity, two recording groups and original-ID selection."""
    source = BwmSource.from_workspace(
        open_workspace(workspace_root),
        coordinate_convention='ibl-mlapdv-um',
    )
    # Bridge snapshots provenance and requires caller-supplied source frame evidence.
    # It preserves every row; clusters use assigned channel locations, not somata.
    first_payload = prepare_bwm_recording(source.insertion(pid_a), frame=bwm_frame)
    second_payload = prepare_bwm_recording(source.insertion(pid_b), frame=bwm_frame)
    with AtlasViewer(
        atlas=atlas_assets,
        anatomy='major' if anatomical_context else 'detailed',
        anatomical_context=anatomical_context,
        mapping='beryl',
        layout='3d',
    ) as app:
        first = app.add_recording(first_payload, name='First', show=('channels',))
        second = app.add_recording(second_payload, name='Second', show=('channels', 'clusters'))
        first.channels.set_visible(False)
        second.clusters.set_visible(False)
        # Hidden or unpositioned rows remain selectable by original source ID.
        # cluster_id must exist in pid_b; it is never interpreted as a row number.
        app.selection.set_observations([second.clusters.observation(cluster_id)])
        app.anatomy.set_mapping('cosmos')  # clears regions, preserves exact cluster selection
        second.clusters.set_visible(True)
        app.show()

    # Metadata-only example: no spike reads and no implicit signal-validation claim.
    # Explicit signal requests stay outside the GUI and use source.spikes(...,
    # requirements=...) with the caller's existing scientific validation requirements.
