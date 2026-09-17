"""Small, fictional TTS auditions; independent of the game's configuration.

Run using .cache/speech-research/venv/Scripts/python.exe. Public community
Spaces can queue, fail, or exhaust their free allocation. No automatic retries.
"""
import argparse
import json
from pathlib import Path
import shutil
import time

from gradio_client import Client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/generated/speech-research"
EN = "I thought I was safe here. I still wake up when I hear a loud noise."
SR = "Mislio sam da sam ovde bezbedan. Još se budim kad čujem jak zvuk."
IJ = "Mislio sam da sam ovdje siguran. Još se budim kad čujem jak zvuk."
CASES = {
    "fish": [
        ("en-angry", "[angry] " + EN),
        ("en-crying", "[crying] " + EN),
        ("sr-sad", "[sad] " + SR),
        ("ijekavian-sad", "[sad] " + IJ),
    ],
    "higgs": [
        ("en-sad", "<|emotion:sadness|> " + EN),
        ("sr-sad", "<|emotion:sadness|> " + SR),
    ],
}
SPACES = {
    "fish": "artificialguybr/fish-s2-pro-zero",
    "higgs": "multimodalart/higgs-audio-v3-tts",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=CASES)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    client = Client(SPACES[args.provider], verbose=False,
                    httpx_kwargs={"timeout": 30})
    for name, text in CASES[args.provider]:
        dest = OUT / f"{args.provider}-{name}.wav"
        if dest.exists():
            print(f"Already exists: {dest.name}", flush=True)
            continue
        record = dict(provider=args.provider, space=SPACES[args.provider],
                      case=name, text=text, reference_voice=None,
                      note="Public hosted demo; not a local GPU benchmark. Unconditioned voice may vary.")
        start = time.perf_counter()
        job = None
        try:
            if args.provider == "fish":
                job = client.submit(text=text, ref_audio=None, ref_text="",
                                    max_new_tokens=512, chunk_length=200,
                                    top_p=0.7, repetition_penalty=1.2,
                                    temperature=0.7, api_name="/tts_inference")
            else:
                job = client.submit(text=text, reference_audio=None, reference_text="",
                                    temperature=0.7, top_p=0.95, top_k=50,
                                    max_new_tokens=512, seed=42, api_name="/synthesize")
            print(f"Submitted {args.provider}/{name}", flush=True)
            result = job.result(timeout=args.timeout)
            if isinstance(result, (tuple, list)):
                result = result[0]
            shutil.copy2(result, dest)
            record.update(status="generated", file=str(dest.relative_to(ROOT)))
        except Exception as exc:
            if job is not None:
                job.cancel()
            record.update(status="failed", error=str(exc))
        record["elapsed_seconds_including_queue"] = round(time.perf_counter() - start, 2)
        records.append(record)
        (OUT / f"{args.provider}-audition-results.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=True), flush=True)
        if record["status"] == "failed":
            break  # Do not repeatedly hit unavailable or quota-limited demos.


if __name__ == "__main__":
    main()
