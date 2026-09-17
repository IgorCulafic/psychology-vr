"""Seed the shared, editable performance catalog used by Unity and the bridge."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[
('neutral','Neutral','Ordinary attentive delivery.',{},0,0,0,0,0,.16,1),
('calm','Calm','Settled and attentive, without implying recovery.',{'MouthSmile':.18,'EyeSquint':.1},0,0,0,0,0,.12,1.3),
('anxious','Anxiety','Uneasy anticipation and guarded attention.',{'BrowWorry':.65,'BrowTense':.18,'MouthFrown':.22},3,0,1,.12,0,.38,.85),
('afraid','Fear','Present fear: widened eyes and a tense mouth.',{'BrowWorry':.65,'BrowRaise':.65,'EyeWide':.8,'MouthWide':.35,'MouthFrown':.55,'JawOpen':.15},-3,0,-2,.25,0,.4,.8),
('panicked','Panic','Overwhelming fear; use sparingly and only when the exchange supports it.',{'BrowWorry':.9,'BrowRaise':.85,'EyeWide':1,'MouthWide':.5,'MouthFrown':.7,'JawOpen':.3},-4,0,-3,.65,0,.55,.65),
('sad','Sadness','Sorrow with lowered gaze and downturned lips.',{'BrowWorry':.9,'MouthFrown':.8,'EyeSquint':.12},12,0,3,0,0,.5,1.1),
('crying','Crying','Visible tears and sobbing; high intensity covers the face with both hands. Not every sad statement is crying.',{'BrowWorry':1,'MouthFrown':.9,'EyeSquint':.85,'BlinkLeft':.25,'BlinkRight':.25,'MouthPress':.25},10,0,4,.8,1,.65,.7),
('angry','Anger','Directed anger with knitted brows and tense lips.',{'BrowTense':1,'EyeSquint':.5,'MouthPress':.8,'NoseWrinkle':.25},-2,0,2,.2,0,.08,1.2),
('frustrated','Frustration','Strained impatience or feeling blocked.',{'BrowTense':.75,'MouthPress':.45,'EyeSquint':.3},2,0,1,.08,0,.3,1),
('disgusted','Disgust','Nose wrinkle, upper-lip lift, and slight recoil.',{'NoseWrinkle':1,'UpperLipRaise':.85,'EyeSquint':.45,'BrowTense':.55,'MouthFrown':.3},-3,9,-3,0,0,.45,1.1),
('happy','Happiness','A positive moment with a smile and softened eyes.',{'MouthSmile':1,'EyeSquint':.35,'BrowRaise':.18},-1,0,-1,0,0,.12,1.1),
('relieved','Relief','Tension eases for the moment; broader difficulties may remain.',{'MouthSmile':.65,'BrowRaise':.12,'EyeSquint':.18},2,0,-1,0,0,.2,1.3),
('surprised','Surprise','Brief unexpected reaction, distinct from fear.',{'BrowRaise':1,'EyeWide':.9,'JawOpen':.3,'MouthPucker':.35},-2,0,-2,0,0,.1,1.6),
('ashamed','Shame','Avoiding attention and looking down.',{'BrowWorry':.6,'MouthPress':.55,'MouthFrown':.3},16,8,4,0,0,.8,.85),
('guilty','Guilt','Troubled regret; do not invent wrongdoing to justify the cue.',{'BrowWorry':.8,'MouthFrown':.55,'MouthPress':.3},9,-5,2,.05,0,.6,1),
('confused','Confusion','Uncertainty and a searching expression.',{'BrowRaiseLeft':.75,'BrowTense':.25,'MouthPucker':.2},1,-6,0,0,0,.3,1),
('skeptical','Skepticism','Doubt or guarded evaluation of what was said.',{'BrowRaiseLeft':1,'EyeSquint':.25,'MouthPress':.5},-2,7,-1,0,0,.2,1.3),
('hopeful','Hope','Tentative optimism, without sudden emotional resolution.',{'MouthSmile':.45,'BrowWorry':.2,'BrowRaise':.25},-2,0,0,0,0,.14,1.1),
('despondent','Despondency','Discouraged, low-energy delivery; a performance state, not a diagnosis.',{'BrowWorry':.45,'MouthFrown':.65,'EyeSquint':.3},15,0,5,0,0,.7,1.6),
('numb','Numbness','Emotionally flat and withdrawn, with little visible movement.',{'EyeSquint':.18,'MouthPress':.12},5,0,3,0,0,.7,1.9),
]
catalog={'version':1,'emotions':[{'name':name,'label':label,'description':desc,
    'shapes':[{'name':n,'weight':w} for n,w in shapes.items()],
    'headPitch':pitch,'headYaw':yaw,'torsoPitch':torso,'tremble':tremble,'tears':tears,
    'lookAwayChance':away,'blinkInterval':blink} for name,label,desc,shapes,pitch,yaw,torso,tremble,tears,away,blink in rows],
    'aliases':[{'name':a,'emotion':e} for a,e in [('fear','afraid'),('disgust','disgusted'),('anger','angry'),('joy','happy'),('surprise','surprised'),('sobbing','crying'),('depressed','despondent')]]}
path=ROOT/'unity/Assets/PsychologyVR/Resources/EmotionCatalog.json'
path.write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
print(path)
