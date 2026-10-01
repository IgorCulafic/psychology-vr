"""Build an offline listening page from the saved, user-selected voice presets."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_ROOT = ROOT / 'voices'


def voice_link(relative):
    path = (ROOT / relative).resolve()
    local = path.relative_to(VOICE_ROOT.resolve())
    if not path.is_file():
        raise FileNotFoundError(path)
    return html.escape(local.as_posix(), quote=True)


def main():
    sections = []
    for person in ['person_01', 'person_02', 'person_03']:
        cards = []
        for path in sorted((VOICE_ROOT / person / 'prepared').glob('preferred_*.json')):
            preset = json.loads(path.read_text(encoding='utf-8'))
            emotion = preset.get('performance_emotion', 'angry').title()
            sample = voice_link(preset['audition_audio'])
            reference = voice_link(preset['reference'])
            label = html.escape(preset['audition_display_label'])
            cards.append(f'<article><h3>{emotion}</h3><p>{label}</p><p>Generated speech</p><audio controls preload="none" src="{sample}"></audio><details><summary>Recorded reference</summary><audio controls preload="none" src="{reference}"></audio></details></article>')
        status = 'Anger, sadness and happiness selected.' if person == 'person_03' else 'Anger selected; other emotional deliveries still need review.'
        sections.append(f'<section><h2>{person.replace("person_0", "Person ")}</h2><p>{status}</p><div class="grid">{"".join(cards)}</div></section>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Psychology VR - Voice library</title>
<style>body{font:17px/1.6 system-ui;background:#f5f1e9;color:#263b36;max-width:1120px;margin:36px auto;padding:0 24px}section{background:white;border:1px solid #ded8cc;padding:24px;border-radius:16px;margin:24px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:24px}audio{width:100%}h3{margin-bottom:8px}summary{cursor:pointer}a{color:#286b59}</style>
<h1>Psychology VR - Voice library</h1><p>Listen to the selected generated performances and compare them with the recorded references. These presets can generate new dialogue; the samples are examples.</p><p>The three speaker packs are available for development. Assigning them to individual patients is still pending. The consultation player continues using its configured shared voice.</p>SECTIONS
<section><h2>Person 3 comparisons</h2><p><a href="auditions/2026-10-01/person-3/index.html">Initial comparison</a> · <a href="auditions/2026-10-01/person-3/refinement-1/index.html">Sadness comparison</a> · <a href="auditions/2026-10-01/person-3/happiness-2/index.html">Happiness comparison</a></p><p>Older comparison pages include rejected candidates as well as selected ones.</p></section></html>'''
    target = VOICE_ROOT / 'index.html'
    target.write_text(page.replace('SECTIONS', ''.join(sections)), encoding='utf-8')
    print('Voice index created; all selected audio paths verified.')


if __name__ == '__main__':
    main()
