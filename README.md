# ibl_datoviz

## Installation
```python
git clone https://github.com/int-brain-lab/ibl-datoviz.git
cd ibl-datoviz
pip install -e .
```

## Create an interactive datoviz app
```python
import datoviz as dvz
from ibl_datoviz.viewer import Viewer

app = dvz.App(background='white')
fig = app.figure(800, 600)
panel = fig.panel()
arcball = panel.arcball()
panel.update()
app.enable_ipython()
```

## Create an 3D brain viewer instance
```python
viewer = Viewer(app, panel)
```

## Add brain regions
```python
viewer.meshes.add_regions(['VISp', 'LGd', 'SCs'], hemisphere='left')
viewer.meshes.set_alpha(150)
```

## Download ephys atlas features table from S3
```python
import pandas as pd
from one.remote import aws
from one.api import ONE
from pathlib import Path
    
def get_features(one) -> pd.DataFrame:
    """
    Download ephys atlas features table from S3.
    
    Returns
    -------
    pd.DataFrame
        The ephys atlas features table.
    """
    # Create folder to store the features table
    table_path = one.cache_dir.joinpath('ephys_atlas_features')
    table_path.mkdir(parents=True, exist_ok=True)
    s3, bucket_name = aws.get_s3_from_alyx(alyx=one.alyx)
    # Download file
    base_path = Path('aggregates/atlas/features/ea_active/2025_W43/agg_full/')
    fname = 'df_all_cols_merged.pqt'
    aws.s3_download_file(base_path.joinpath(fname), table_path.joinpath(fname), s3=s3,
                         bucket_name=bucket_name)
    data = pd.read_parquet(table_path.joinpath('df_all_cols_merged.pqt')).reset_index()
    return data

features = get_features(ONE())
```

## Add cluster points from ephys atlas features
```python
xyz = features[['x', 'y', 'z']].values
rms_ap = features['rms_ap'].values
viewer.points.add_points(xyz, rms_ap, sizes=2, cmap='plasma')
```

## Add insertions from ephys atlas features
```python
from iblatlas.atlas import Insertion
import numpy as np

pids = features.pid.unique()[0:10]
ins = []
for pid in pids:
    feat = features[features.pid == pid]
    ins.append(Insertion.from_track(np.c_[feat.x, feat.y, feat.z], brain_atlas=viewer.meshes.model.ba).xyz)

viewer.insertions.add_insertions(ins, pids, [10] * 10, [[0, 0, 255, 255]] * 10)
```