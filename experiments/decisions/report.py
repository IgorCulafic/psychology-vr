"""Snapshot completed local runs and generate a readable comparison."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'services/.runtime/decision-eval'
DEST = Path(__file__).resolve().parent/'results'
NAMES = {'baseline':'Current Qwen interpreter', 'decider':'Decider 2B',
         'gliclass':'GLiClass Multilang Mini', 'simple':'Simple Jev + Qwen 0.8B',
         'laya':'Laya Multilingual'}

def main():
    runs = {key:json.loads((SOURCE/f'{key}.json').read_text(encoding='utf-8')) for key in NAMES}
    hashes = {r['metadata']['fixture_sha256'] for r in runs.values()}
    assert len(hashes)==1, 'Fixture changed between runs'
    assert all(len(r['records'])==56 and 'summary' in r['metadata'] for r in runs.values()), 'Incomplete run'
    DEST.mkdir(exist_ok=True)
    for key, run in runs.items():
        (DEST/f'{key}.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['# Local decision-model results — 21 September 2026', '',
      'Small development screen: 56 authored cases, RTX 5090, Windows, no paid inference. '
      'See [protocol](../README.md) for setup and limitations.', '',
      '| Configuration | Event correct | Topic correct | Detail correct | All 3 correct | Median | p95 | Peak CUDA allocated |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for key, run in runs.items():
        s=run['metadata']['summary']['all']; n=s['n']
        counts=[sum(r['correct'][f] for r in run['records']) for f in ['event','topic','invites_detail']]
        exact=sum(all(r['correct'].values()) for r in run['records'])
        mem='Separate server' if key=='baseline' else f"{run['metadata']['cuda_peak_allocated_mib']/1024:.2f} GiB"
        lines.append(f"| {NAMES[key]} | {counts[0]}/{n} | {counts[1]}/{n} | {counts[2]}/{n} | {exact}/{n} | {s['median_ms']:.0f} ms | {s['p95_ms']:.0f} ms | {mem} |")
    lines += ['', '## Language split', '',
      '| Configuration | English event / all fields | Montenegrin event / all fields | Without diacritics event / all fields |',
      '|---|---:|---:|---:|']
    for key,run in runs.items():
        parts=[]
        for lang in ['en','cnr','cnr-ascii']:
            s=run['metadata']['summary'][lang]
            parts.append(f"{100*s['field_accuracy']['event']:.0f}% / {100*s['exact_accuracy']:.0f}% (n={s['n']})")
        lines.append('| '+NAMES[key]+' | '+' | '.join(parts)+' |')
    lines += ['', '## Errors to review', '',
      'These include debatable taxonomy boundaries; the JSON records retain all accepted '
      'labels and raw scores. Inspect the consequential failures rather than relying only on averages.', '']
    for key,run in runs.items():
        lines += [f'### {NAMES[key]}', '']
        for row in run['records']:
            if all(row['correct'].values()): continue
            errors='; '.join(f"{f}: got {row['prediction'].get(f)!r}, expected {row['expected'][f]!r}"
                            for f,ok in row['correct'].items() if not ok)
            lines.append(f"- **{row['id']}** — {row['text']} → {errors}")
        lines.append('')
    (DEST/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines[:12]))

if __name__=='__main__': main()
