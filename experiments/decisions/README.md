# Free local decision-model screen

This experiment evaluates the interpreter that reads a counsellor's utterance and
sets `event`, `topic`, and `invites_detail`. It does **not** replace patient dialogue,
speech recognition, TTS, or the authored relationship dynamics. Nothing here changes
the live game configuration. All inference is local; no paid API or private data upload.

## Reproduce

Run from the repository root, using an isolated Python 3.12 environment:

```powershell
uv venv .tools/decision-eval-venv --python 3.12
uv pip install --python .tools/decision-eval-venv/Scripts/python.exe torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .tools/decision-eval-venv/Scripts/python.exe -r experiments/decisions/requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cu128
```

The lock records the tested Windows environment. CUDA 12.8 PyTorch supports the
RTX 5090 used here. CPU execution is available through `--device cpu`, but timings
will differ. Decider uses its eager path without CUDA graphs or optional Triton/FLA.

Download with the Hugging Face CLI (`uv tool install huggingface-hub`, or an existing `hf`):

```powershell
hf download convaiinnovations/laya-multilingual --revision 052592a15d198d9ad47da779604259b10b47b7aa --local-dir .cache/models/decisions/laya-multilingual
hf download Mapika/decider-2b --revision b37f7e1ba3fbc9238004cf531fabbee2619973fd --local-dir .cache/models/decisions/decider-2b
hf download knowledgator/gliclass-multilang-mini --revision 0bd888b6c3ef9fca5f0a9d407bddfbbc7623486b --local-dir .cache/models/decisions/gliclass-mini
hf download Qwen/Qwen3.5-0.8B --revision 2fc06364715b967f1860aea9cf38778875588b17 --local-dir .cache/models/decisions/qwen-0.8b
```

Put the source root of [Decider commit c4daaac](https://github.com/Mapika/decider/tree/c4daaac)
at `.tools/decider`, and [Simple Jev commit b02aa81](https://github.com/featherless-ai/simple-jev/tree/b02aa81)
at `.tools/simple-jev`. No editable package installation is required: the harness
imports those checkouts explicitly. These sources and the candidate models use
Apache 2.0 licenses; preserve their notices when redistributing. Weights and runtimes
are intentionally excluded from Git.

```powershell
# Smoke test, then full run; run models sequentially to avoid GPU contention.
.tools/decision-eval-venv/Scripts/python.exe experiments/decisions/benchmark.py --backend decider --limit 4 --suffix=-smoke
.tools/decision-eval-venv/Scripts/python.exe experiments/decisions/benchmark.py --backend decider
# Repeat with laya, gliclass, and simple.

# Existing local Qwen interpreter (requires the normal project model/config).
./tools/launch.ps1 -ModelOnly
.tools/decision-eval-venv/Scripts/python.exe experiments/decisions/benchmark.py --backend baseline

# Build a reviewable report and snapshot the five full runs.
.tools/decision-eval-venv/Scripts/python.exe experiments/decisions/report.py
```

Results and Inspect AI audit logs go into `services/.runtime/decision-eval/`.
Inspect uses a mock provider only to host a custom solver: it never calls a hosted
LLM. Its unavailable Windows Unix-socket control surface produces a harmless
warning; sample execution and audit logs work. Inspect scratch paths are redirected
inside the project because Windows known-folder APIs ignore `LOCALAPPDATA` overrides.

## Protocol and limits

- 56 fictional, authored checks: 25 paired English/Montenegrin scenarios and six
  Montenegrin variants without diacritics. Expected labels were fixed before model
  comparison; overlapping categories have explicit acceptable alternatives.
- These are development checks, **not** a representative language benchmark or
  clinical validation. Related translations are not independent samples. There are
  no multi-session trajectories, spoken audio, or long histories in this screen.
- Candidates receive the same short state and descriptive label definitions.
  GLiClass uses native dialogue classification rather than an instruction rubric;
  it is not an instruction-following model. The initial rubric-based smoke run was
  unsuccessful; the full run uses the native adapter recorded in its metadata.
- Laya's token preflight confirms all question heads fit its native 256-token
  budget. No question options are silently removed. State examples are short.
- Baseline calls the existing `Bridge.appraise` with the production prompt and Ivan
  profile. It has a longer, project-specific prompt and examples. This compares
  practical configurations, **not** isolated model capability under identical prompts.
- Warmup excluded; one measured call per case, sequential, one model process at a
  time. Timings cover all three fields; baseline includes localhost HTTP/context
  checks. They are appraisal latency, **not** total spoken-response latency.
  The last six baseline cases had a latency spike (roughly 7.5–20.2 seconds).
  Its cause was not isolated; do not interpret that ordering effect as evidence
  that removing diacritics inherently slows inference.
- CUDA allocated memory is measured by PyTorch in each candidate process, including
  model weights. It excludes driver/runtime overhead and other applications. The
  baseline runs in a separate llama.cpp process, so its PyTorch counter cannot
  measure that server's GPU memory.
- Model confidence is not validated as a probability of correctness on this task.
  Do not use a guessed confidence threshold to control anger or leaving the room.
- `simple-direct` is a diagnostic adapter using the same compiled prompts and
  weights with independent uncached forwards. It reproduced the default-option
  failure on four targeted cases; it is not included as a fifth candidate.

## Decision after this screen

Keep the current interpreter. It got all three fields right in 54/56 cases,
versus 33/56 for Decider, 20/56 for GLiClass, 9/56 for Simple Jev + 0.8B, and
8/56 for Laya. [Full results and errors](results/REPORT.md).

Decider is the best candidate for further work: approximately 66 ms median for
all three fields and 3.71 GiB peak allocated CUDA memory. However, it classified
defending the patient as an attack, mishandled coerced disclosure, and missed
several Montenegrin invitations to elaborate. Those errors would damage the
conversation even though its 47/56 event score looks promising.

The next useful step would be a larger, human-reviewed local-language dataset,
with held-out conversations, followed by prompt/adapter improvements or local
fine-tuning and a fresh evaluation. No training or production integration was
performed in this experiment. A confidence-based fallback needs validation,
including confident mistakes, before it can replace the existing interpreter.

## Sources

- [Laya Multilingual](https://huggingface.co/convaiinnovations/laya-multilingual): its
  card explicitly reports weak zero-shot typed decisions and uncalibrated scores.
- [Decider 2B](https://huggingface.co/Mapika/decider-2b): English-focused model;
  Montenegrin results here are experimental.
- [GLiClass Multilang Mini](https://huggingface.co/knowledgator/gliclass-multilang-mini).
- [Simple Jev](https://github.com/featherless-ai/simple-jev) with
  [Qwen3.5 0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B): a framework plus a chosen
  model, not the proprietary Jev model or evidence of parity with it.
