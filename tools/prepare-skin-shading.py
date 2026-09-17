"""Create restrained specular/smoothness maps from existing skin normal-map detail."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
root=Path(__file__).resolve().parents[1]
source=root/'unity/Assets/PsychologyVR/Art/Characters/Candidates/Jumper/textures'
out=root/'unity/Assets/PsychologyVR/Art/Characters/SkinDetail'
out.mkdir(parents=True,exist_ok=True)
for normal in source.glob('Std_Skin_*_Normal.png'):
    image=Image.open(normal).convert('RGB').resize((1024,1024),Image.Resampling.LANCZOS)
    detail=np.asarray(image,dtype=np.float32)[:,:,:2]/127.5-1
    slope=np.sqrt((detail**2).sum(axis=2))
    # This is an authored roughness treatment, not a measured skin roughness scan.
    variation=Image.fromarray(np.uint8(np.clip(slope*3,0,1)*255)).filter(ImageFilter.GaussianBlur(2))
    smoothness=np.uint8((.29-.10*np.asarray(variation,dtype=np.float32)/255)*255)
    rgba=np.empty((1024,1024,4),dtype=np.uint8)
    rgba[:,:,:3]=7  # Linear dielectric reflectance about 0.027, below the Lit default 0.04.
    rgba[:,:,3]=smoothness
    Image.fromarray(rgba).save(out/(normal.stem.replace('_Normal','')+'_spec_smooth.png'))
print('Prepared 4 skin specular/smoothness maps; original skin textures untouched.')
