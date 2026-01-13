from ibl_datoviz.meshes import BrainMeshController, BrainMeshModel
from ibl_datoviz.points import PointsController
from ibl_datoviz.insertions import InsertionController

class Viewer:
    def __init__(self, app, panel):

        model = BrainMeshModel()
        self.offset = model.load_mesh(997)[0].mean(axis=0)
        self.scale = 200
        self.points = PointsController(app, panel, self.offset, scale=self.scale)
        self.insertions = InsertionController(app, panel, self.offset, scale=self.scale)
        self.meshes = BrainMeshController(app, panel, self.offset, scale=self.scale, model=model)
        self.meshes.add_root()
