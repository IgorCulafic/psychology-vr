"""Generate local Fish S2 Pro auditions and record reproducible runtime metrics.

Use .tools/fish-speech/.venv/Scripts/python.exe to run this file.
This harness does not change the game's speech provider.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FISH = ROOT / ".tools/fish-speech"
MODEL = ROOT / ".cache/fish-s2-pro"
OUT = ROOT / "docs/generated/fish-local"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("DO_NOT_TRACK", "1")
sys.path.insert(0, str(FISH))

LINE = "I didn't expect you to say that. I need a moment."
CASES = [
    ("en-neutral", "English / neutral", LINE),
    ("en-sad", "English / sad", "[sad] " + LINE),
    ("en-angry", "English / angry", "[angry] " + LINE),
    ("en-crying", "English / crying", "[crying] [sobbing] " + LINE),
    ("en-fear", "English / fear", "[scared] [trembling voice] " + LINE),
    ("en-disgust", "English / disgust", "[disgusted] " + LINE),
    ("sr-sad", "Serbian, Latin / sad", "[sad] Mislio sam da sam ovde bezbedan. Još se budim kad čujem jak zvuk."),
    ("sr-cyrillic-angry", "Serbian, Cyrillic / angry", "[angry] Зашто ме нисте слушали? Рекао сам вам да нисам спреман да причам о томе."),
    ("hr-bs-sad", "Croatian / Bosnian wording / sad", "[sad] Mislio sam da sam ovdje siguran. Još se budim kad čujem jak zvuk."),
    ("cnr-experimental", "Montenegrin wording / experimental", "[sad] Nijesam spreman da pričam o tome. Treba mi još malo vremena."),
]


def gpu_snapshot():
    return subprocess.check_output([
        "nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
        "--format=csv,noheader"], text=True).strip()


def save_report(report, output):
    (output / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    cards = []
    for r in report["samples"]:
        cards.append(f'<article><h2>{html.escape(r["label"])}</h2>'
                     f'<p>{html.escape(r["text"])}</p>'
                     f'<audio controls preload="metadata" src="{html.escape(r["file"])}"></audio>'
                     f'<small>{r["duration_seconds"]:.2f}s audio · {r["generation_seconds"]:.2f}s generation · '
                     f'{r["real_time_factor"]:.2f}× duration</small></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AUDITION_TITLE</title>
<style>body{font:17px system-ui;background:#f6f1e9;color:#302b27;max-width:1050px;margin:40px auto;padding:0 24px}
h1{font-size:34px}h2{font-size:20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}
article{background:white;border:1px solid #ded4c7;border-radius:14px;padding:22px}audio{width:100%;margin:10px 0}
small{display:block;color:#655e57}header{margin-bottom:30px}p{line-height:1.5}</style>
<header><h1>AUDITION_TITLE</h1>
<p>AUDITION_DESCRIPTION</p>
REFERENCE_BLOCK
<details><summary>Generation details</summary><p>Native Windows, BF16, no compilation, 4096-token context. GPU: GPU_NAME.
Generation times exclude model loading and are not streaming first-audio latency.</p>
<p>Regional pronunciation and emotional quality need listening assessment.</p></details></header><main>CARDS</main></html>'''
    page = page.replace("GPU_NAME", html.escape(report["gpu"])).replace("CARDS", "".join(cards))
    reference_block = (f'<p>Voice reference: {html.escape(report["reference"])}</p><audio controls preload="metadata" src="reference.wav"></audio>'
                       if report.get("reference") else '<p>No voice reference. Voice and language cues are supplied in the prompt.</p>')
    page = page.replace("REFERENCE_BLOCK", reference_block)
    page = page.replace("AUDITION_TITLE", html.escape(report.get("title", "Fish S2 Pro · local auditions")))
    page = page.replace("AUDITION_DESCRIPTION", html.escape(report.get("description", "Same synthetic voice reference and seed across samples. English comparisons use the same words. Emotion names describe the requested performance, not a verified quality rating.")))
    if output.name == "fish-reference":
        navigation = '<p><a href="../index.html">Compare with the existing Alex voice reference</a></p>'
    elif (output / "fish-reference/results.json").exists():
        navigation = '<p><a href="fish-reference/index.html">Compare with the earlier Fish voice reference</a></p>'
    else:
        navigation = ""
    page = page.replace("</header>", navigation + "</header>")
    (output / "index.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="all", help="Comma-separated case IDs or all")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--reference", type=Path, default=ROOT / "unity/Assets/PsychologyVR/Resources/FaceDemo/speech.wav")
    parser.add_argument("--reference-text", help="Exact transcript; defaults to the reference's matching .json file")
    parser.add_argument("--no-reference", action="store_true", help="Generate from text cues without a reference accent/voice")
    parser.add_argument("--case-file", type=Path, help="JSON object with description and cases [{id, label, text}]")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.7)
    parser.add_argument("--sampling-profiles", type=Path, help="JSON list of {id, label, temperature, top_p}; compare profiles with one model load")
    args = parser.parse_args()
    case_config = json.loads(args.case_file.read_text(encoding="utf-8")) if args.case_file else {}
    case_catalog = [(c["id"], c["label"], c["text"]) for c in case_config["cases"]] if case_config else CASES
    selected = case_catalog if args.cases == "all" else [c for c in case_catalog if c[0] in args.cases.split(",")]
    if not selected:
        parser.error("No matching cases")
    profiles = json.loads(args.sampling_profiles.read_text(encoding="utf-8")) if args.sampling_profiles else [
        dict(id="", label="", temperature=args.temperature, top_p=args.top_p)]
    if not profiles or len({p["id"] for p in profiles}) != len(profiles):
        parser.error("Sampling profiles must be nonempty and have unique IDs")
    for profile in profiles:
        if (not 0 < profile["temperature"] < 2 or not 0 < profile["top_p"] <= 1
                or (args.sampling_profiles and (not profile["id"] or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in profile["id"])))):
            parser.error("Invalid sampling profile ID, temperature, or top_p")
    jobs = [(case, profile) for case in selected for profile in profiles]
    args.output.mkdir(parents=True, exist_ok=True)
    import numpy as np
    import soundfile as sf
    import torch
    from loguru import logger
    from fish_speech.models.text2semantic.llama import DualARTransformer
    from fish_speech.models.text2semantic.inference import (
        decode_one_token_ar, generate_long, load_codec_model, encode_audio, decode_to_audio,
    )

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this audition; refusing silent CPU fallback")
    torch.set_num_threads(8)
    logger.add(str(args.output / "inference.log"), encoding="utf-8")
    reference = None if args.no_reference else args.reference.resolve()
    reference_text = None
    if reference:
        reference_text = args.reference_text or json.loads(reference.with_suffix(".json").read_text(encoding="utf-8"))["text"]
        shutil.copy2(reference, args.output / "reference.wav")
    revision = subprocess.check_output(["git", "-C", str(FISH), "rev-parse", "HEAD"], text=True).strip()
    metadata = MODEL / ".cache/huggingface/download/config.json.metadata"
    report = dict(date=datetime.now(timezone.utc).isoformat(), model="fishaudio/s2-pro",
                  model_revision=metadata.read_text().splitlines()[0] if metadata.exists() else None,
                  source_revision=revision, gpu=torch.cuda.get_device_name(),
                  platform=platform.platform(), python=sys.version, torch=torch.__version__,
                  precision="bfloat16", compilation=False, context_tokens=4096, seed=42,
                  temperature=args.temperature, top_p=args.top_p, top_k=30,
                  reference=str(reference.relative_to(ROOT)) if reference else None, reference_text=reference_text,
                  reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest() if reference else None,
                  gpu_before=gpu_snapshot(), samples=[])
    if args.sampling_profiles:
        report["sampling_profiles"] = profiles
        report["temperature"] = report["top_p"] = None
    if case_config.get("description"):
        report["description"] = case_config["description"]
    if case_config.get("title"):
        report["title"] = case_config["title"]
    with torch.inference_mode():
        started = time.perf_counter()
        print("Loading Fish S2 Pro and codec locally...", flush=True)
        model = DualARTransformer.from_pretrained(MODEL, load_weights=True, max_length=4096)
        model = model.to(device="cuda", dtype=torch.bfloat16).eval()
        model.fixed_temperature = torch.tensor(args.temperature, device="cuda", dtype=torch.float)
        model.fixed_top_p = torch.tensor(args.top_p, device="cuda", dtype=torch.float)
        model.fixed_repetition_penalty = torch.tensor(1.5, device="cuda", dtype=torch.float)
        model._cache_setup_done = False
        codec = load_codec_model(MODEL / "codec.pth", "cuda", torch.bfloat16)
        prompt_codes = encode_audio(reference, codec, "cuda").cpu() if reference else None
        torch.cuda.synchronize()
        report["load_and_reference_seconds"] = round(time.perf_counter() - started, 3)
        report["gpu_after_load"] = gpu_snapshot()
        save_report(report, args.output)
        for (base_case_id, base_label, text), profile in jobs:
            case_id = f'{base_case_id}-{profile["id"]}' if profile["id"] else base_case_id
            label = f'{base_label} · {profile["label"]}' if profile["label"] else base_label
            temperature, top_p = profile["temperature"], profile["top_p"]
            model.fixed_temperature.fill_(temperature)
            model.fixed_top_p.fill_(top_p)
            print(f"AUDITION_START {case_id}", flush=True)
            torch.manual_seed(42)
            torch.cuda.manual_seed_all(42)
            torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            codes = []
            for response in generate_long(
                    model=model, device="cuda", decode_one_token=decode_one_token_ar,
                    text="<|speaker:0|>" + text, max_new_tokens=512,
                    top_p=top_p, top_k=30, temperature=temperature, compile=False,
                    chunk_length=300, prompt_text=[reference_text] if reference else None,
                    prompt_tokens=[prompt_codes] if reference else None):
                if response.action == "sample":
                    codes.append(response.codes)
            if not codes:
                raise RuntimeError(f"No speech generated for {case_id}")
            merged = torch.cat(codes, dim=1)
            audio = decode_to_audio(merged, codec).float().cpu().numpy()
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - start
            if not len(audio) or not np.isfinite(audio).all():
                raise RuntimeError(f"Invalid waveform for {case_id}")
            peak = float(np.abs(audio).max())
            gain = min(1.0, 0.98 / max(peak, 1e-8))
            filename = f"{case_id}.wav"
            sf.write(args.output / filename, audio * gain, codec.sample_rate, subtype="PCM_16")
            duration = len(audio) / codec.sample_rate
            row = dict(id=case_id, label=label, text=text, file=filename,
                       base_case_id=base_case_id, sampling_profile=profile["id"] or "custom",
                       temperature=temperature, top_p=top_p, top_k=30, seed=42,
                       duration_seconds=round(duration, 3), generation_seconds=round(elapsed, 3),
                       real_time_factor=round(elapsed / duration, 3), codec_tokens=int(merged.shape[1]),
                       sample_rate=codec.sample_rate, raw_peak=peak, output_gain=gain,
                       rms=float(np.sqrt(np.mean(audio**2))),
                       peak_allocated_mib=round(torch.cuda.max_memory_allocated()/1024**2, 1),
                       peak_reserved_mib=round(torch.cuda.max_memory_reserved()/1024**2, 1),
                       gpu_after=gpu_snapshot(), cold_first_sample=not report["samples"])
            report["samples"].append(row)
            save_report(report, args.output)
            print("AUDITION_OK " + json.dumps(row, ensure_ascii=True), flush=True)
    print(f"Finished: {args.output / 'index.html'}", flush=True)


if __name__ == "__main__":
    main()
