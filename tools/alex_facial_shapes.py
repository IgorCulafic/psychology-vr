"""Original facial deformations for the supplied CC BY Alex mesh.
Landmarks are in the original glTF's metre-scaled Blender rest coordinates.
No player avatar geometry is changed by this module.
"""
import bpy,math,json,heapq
from mathutils import Vector,Matrix

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def bell(x,c,r):return math.exp(-((x-c)/r)**2*2)

def add_facial_shapes(meshes,report_path):
    report=[]
    for obj in meshes:
        names=' '.join(m.name for m in obj.data.materials)
        skin='Wolf3D_Skin' in names;eye='Wolf3D_Eye' in names;teeth='Wolf3D_Teeth' in names
        if not (skin or eye or teeth):continue
        obj.shape_key_add(name='Basis')
        rest=[obj.matrix_world@v.co for v in obj.data.vertices]; inv=obj.matrix_world.inverted()
        cx=sum(p.x for p in rest)/len(rest) if eye else 0
        eye_center=Vector((cx,-.08942,1.72620))
        mouth_weights={}
        if skin:
            # Geodesic distances distinguish the two folded lip surfaces even
            # where they almost touch in rest space. A height cut tears the lip.
            keys={};points=[];indices=[]
            for p in rest:
                k=tuple(round(v,7) for v in p)
                if k not in keys:keys[k]=len(points);points.append(p)
                indices.append(keys[k])
            valid={i for i,p in enumerate(points) if abs(p.x)<.043 and 1.639<p.z<1.677 and p.y<-.084}
            adj={i:{} for i in valid}
            for edge in obj.data.edges:
                a,b=[indices[i] for i in edge.vertices]
                if a in valid and b in valid and a!=b:
                    distance=(points[a]-points[b]).length;adj[a][b]=distance;adj[b][a]=distance
            def distances(lower):
                seeds=[i for i in valid if abs(points[i].x)<.025 and points[i].y<-.115 and
                       ((1.645<points[i].z<1.6535) if lower else (1.661<points[i].z<1.669))]
                dist={i:0 for i in seeds};queue=[(0,i) for i in seeds];heapq.heapify(queue)
                while queue:
                    d,i=heapq.heappop(queue)
                    if d!=dist[i]:continue
                    for j,length in adj[i].items():
                        value=d+length
                        if value<dist.get(j,1e6):dist[j]=value;heapq.heappush(queue,(value,j))
                return dist
            lower,upper=distances(True),distances(False)
            for i in valid:
                if i in lower and i in upper:
                    w=upper[i]/max(1e-9,lower[i]+upper[i])
                    mouth_weights[tuple(round(v,7) for v in points[i])]=smooth(.25,.75,w)
        def shape(name,operation):
            key=obj.shape_key_add(name=name);largest=0;changed=0
            for i,p in enumerate(rest):
                q=operation(p.copy());delta=(q-p).length;largest=max(largest,delta)
                if delta>1e-6:changed+=1
                key.data[i].co=inv@q
            key.value=0
            report.append({'mesh':obj.name,'shape':name,'changed_vertices':changed,'max_displacement_m':largest})
        def jaw(p):
            # Separate the lower lip at its actual seam, preserving the upper lip.
            w=1-smooth(1.653,1.663,p.z)
            if skin:
                local=mouth_weights.get(tuple(round(v,7) for v in p),w)
                influence=1-smooth(.028,.043,abs(p.x));w=w*(1-influence)+local*influence
            w*=smooth(1.584,1.618,p.z)*(1-smooth(-.01,.05,p.y))
            if teeth:w=1-smooth(1.655,1.658,p.z)
            pivot=Vector((0,.012,1.686));rot=Matrix.Rotation(.14*w,3,'X')
            return pivot+rot@(p-pivot)
        if skin or teeth:shape('JawOpen',jaw)
        if skin:
            def mouth(p,kind):
                w=bell(p.x,0,.048)*bell(p.z,1.658,.020)*(1-smooth(-.100,-.075,p.y))
                if kind=='Pucker':p.x*=1-.30*w;p.y-=.008*w
                if kind=='Wide':p.x*=1+.19*w
                if kind=='Press':p.z+=(1.658-p.z)*.28*w
                if kind=='Smile':p.z+=.009*bell(abs(p.x),.029,.023)*bell(p.z,1.659,.022)*w;p.x*=1+.08*w
                if kind=='Frown':p.z-=.008*bell(abs(p.x),.028,.020)*bell(p.z,1.659,.020)*w
                return p
            for name in ['Pucker','Wide','Press','Smile','Frown']:shape('Mouth'+name,lambda p,n=name:mouth(p,n))
            def brow(p,kind):
                w=bell(abs(p.x),.030,.027)*bell(p.z,1.749,.018)*(1-smooth(-.08,-.04,p.y))
                inner=1-smooth(.014,.046,abs(p.x))
                if kind=='Worry':p.z+=.009*w*inner;p.x*=1-.08*w*inner
                if kind=='Tense':p.z-=.006*w*(.4+.6*inner);p.x*=1-.10*w
                if kind=='Raise':p.z+=.006*w
                return p
            for name in ['Worry','Tense','Raise']:shape('Brow'+name,lambda p,n=name:brow(p,n))
            shape('BrowRaiseLeft',lambda p:brow(p,'Raise') if p.x>0 else p)
            def upper_lip(p):
                upper=1-mouth_weights.get(tuple(round(v,7) for v in p),1-smooth(1.654,1.663,p.z))
                w=bell(p.x,0,.035)*bell(p.z,1.664,.018)*(1-smooth(-.107,-.080,p.y))*upper
                p.z+=.008*w;p.y-=.001*w;return p
            shape('UpperLipRaise',upper_lip)
            def nose_wrinkle(p):
                w=bell(abs(p.x),.013,.014)*bell(p.z,1.689,.014)*(1-smooth(-.106,-.077,p.y))
                p.z+=.005*w;p.y-=.0015*w;p.x*=1+.12*w;return p
            shape('NoseWrinkle',nose_wrinkle)
            def eye_wide(p):
                w=bell(abs(p.x),.032,.026)*(1-smooth(-.099,-.083,p.y))
                p.z+=.0035*w*bell(p.z,1.731,.007)-.0015*w*bell(p.z,1.719,.005)
                return p
            shape('EyeWide',eye_wide)
            def blink(p,side):
                if p.x*side<0:return p
                w=(1-smooth(.018,.030,abs(p.x-side*.032)))*(1-smooth(-.098,-.083,p.y))
                upper=smooth(1.722,1.729,p.z)*(1-smooth(1.734,1.747,p.z))
                lower=bell(p.z,1.718,.006)
                p.z+=w*(-.0095*upper+.0020*lower)
                p.y-=w*.0025*max(upper,lower)
                return p
            shape('BlinkLeft',lambda p:blink(p,1));shape('BlinkRight',lambda p:blink(p,-1))
            def squint(p):
                w=bell(abs(p.x),.032,.026)*bell(p.z,1.718,.013)*(1-smooth(-.10,-.075,p.y))
                p.z+=.0025*w;return p
            shape('EyeSquint',squint)
        if eye:
            side='Left' if cx>0 else 'Right'
            def close(p):p.z=1.723+(p.z-1.7262)*.30;p.y+=.003;return p
            shape('Blink'+side,close)
            for name,angle,axis in [('EyeLookLeft',.17,'Z'),('EyeLookRight',-.17,'Z'),('EyeLookUp',-.12,'X'),('EyeLookDown',.12,'X')]:
                shape(name,lambda p,a=angle,ax=axis:eye_center+Matrix.Rotation(a,3,ax)@(p-eye_center))
    report_path.write_text(json.dumps(report,indent=2))
    return report
