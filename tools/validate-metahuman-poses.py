"""Check the exported Unity joint poses after replacing or rebaking a character."""
import json,re,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
cast=json.loads((ROOT/'experiments/metahuman/cast.json').read_text())['characters']
for cid in sys.argv[1:] or [c['id'] for c in cast]:
    character=next(c for c in cast if c['id']==cid)
    path=ROOT/f'unity/Assets/PsychologyVR/Art/MetaHumans/{cid}/FacialPoses.asset'
    parts=path.read_text().split('\n  - name: ')[1:]
    pattern=r'\{x: ([^,]+), y: ([^,]+), z: ([^,}]+)(?:, w: ([^}]+))?\}'
    def numbers(s):return np.array([[float(v) for v in t if v] for t in re.findall(pattern,s)])
    rows=[];baseline=None
    for chunk in parts:
        name=chunk.splitlines()[0]
        pos=numbers(chunk.split('    positions:')[1].split('    rotations:')[0])
        rot=numbers(chunk.split('    rotations:')[1].split('  afraid:')[0])
        assert pos.shape==(846,3),(name,pos.shape)
        assert rot.shape==(846,4),(name,rot.shape)
        assert np.isfinite(pos).all() and np.isfinite(rot).all()
        assert np.max(abs(np.linalg.norm(rot,axis=1)-1))<.001
        if baseline is None:baseline=(pos,rot)
        moving=bool(np.max(abs(pos-baseline[0]))>1e-5 or np.max(1-abs(np.sum(rot*baseline[1],axis=1)))>1e-5)
        assert name=='neutral' or moving,name
        rows.append(dict(name=name,moving=moving))
    assert len(rows)==21
    result=dict(id=cid,preset=character['preset'],asset_name=character['asset_name'],bones=846,poses=rows)
    (ROOT/f'experiments/metahuman/exports/unity/{cid}-pose-validation.json').write_text(json.dumps(result,indent=2))
    print(f'PASS: {cid}, {character["preset"]}, 846 joints, 20 moving expression/speech poses.')
