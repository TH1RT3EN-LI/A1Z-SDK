#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json
import numpy as np
import omni.kit.app
import omni.kit.async_engine
import omni.usd
ROOT_DIR=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from a1z_ext.runtime.d405.asset import _matrix_from_np
from pxr import UsdGeom, Sdf

async def startup():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        stage = omni.usd.get_context().new_stage()
    prim_path = Sdf.Path('/World/TestXform')
    x = UsdGeom.Xform.Define(stage, prim_path)
    xf = UsdGeom.Xformable(x.GetPrim())
    op = xf.AddTransformOp()
    m = np.array([[1.,2.,3.,4.],[5.,6.,7.,8.],[9.,10.,11.,12.],[0.,0.,0.,1.]], dtype=float)
    gm = _matrix_from_np(m)
    op.Set(gm)
    got = op.Get()
    rows = [[float(got[r][c]) for c in range(4)] for r in range(4)]
    print(json.dumps({'matrix_rows': rows}, ensure_ascii=True))
    omni.kit.app.get_app().post_quit()

omni.kit.async_engine.run_coroutine(startup())
