# Model Lab

Model Lab compares candidate dialogue models using the same authored questions,
character profiles and application pipeline. Open **Start Model Lab.cmd** and
visit **http://127.0.0.1:8797/**. It needs Python 3.11+ and no extra packages.
Start the intended llama.cpp model first; the lab does not download weights,
start a different model or change `services/config.local.json`.

## Running a comparison

The [27 September comparison report](MODEL_COMPARISON_2026-09-27.md) contains actual
local results for six candidates, saved replies and targeted follow-up tests.

The browser is optional. To run downloaded candidates sequentially from PowerShell:

```powershell
./.tools/python/cpython-3.11-windows-x86_64-none/python.exe tools/benchmark-candidates.py --manifest docs/generated/dialogue-candidates.json --models zora113-q6 qwen35-9b-q6 --languages bs cnr --seeds 42 --cases full --output services/.runtime/candidate-comparison/my-comparison
```

Use Python 3.11+ if the bundled development interpreter is elsewhere. The manifest
records public model repositories, pinned revisions, local filenames, sizes and
SHA-256 hashes. Download those weights first with `hf download REPO FILE --revision
REVISION --local-dir DIRECTORY`; the runner checks their hashes before loading.
It starts one owned llama.cpp server at a time on port 8088, refuses an occupied
port, runs a small generation check, then executes the selected suite. It stops
its server after each model. It never replaces the production model setting.

Each batch needs a fresh output directory. `batch.json` records commands, model
identities, progress, device-wide GPU samples and summaries; per-model result JSON
and server logs are retained there. Detailed sessions live under
`services/.runtime/candidate-comparison/runs/`. The runner uses the same evaluation
worker as the UI. Stop with Ctrl+C in the foreground terminal; allow an in-flight
request to finish. Use `--cases quick` for a screen, or explicit scenario IDs and
`--seeds 123` for targeted repeat tests.

For the optional browser workflow:

1. Load one model on the local llama.cpp server, normally port 8087. Keep the same
   context size, GPU offload, runtime and hardware when practical. Record deviations.
2. Open the lab and refresh the detected model. Choose a descriptive label such as
   `Bonsai 2 PQ2 — thinking off — 4096 context`.
3. Start with **Quick screen**: 3 scenarios / 13 turns per language and seed.
   **Full suite** is 16 scenarios / 70 turns per language and seed. Five languages
   and three seeds therefore schedule 1,050 turns, not 70.
4. For an initial comparison, use Bosnian and Montenegrin, seed 42. Then repeat
   promising models with seeds 123 and 2026 and the other required languages.
5. Avoid simultaneous model chats. Each scenario gets a fresh session; history is
   retained inside that scenario. A timeout/error stops that conversation, marks
   its remaining turns skipped and continues the next independent scenario.
6. Load the next model, refresh detection, and repeat the same selection. Model
   identity/settings are checked before each turn to prevent mixing models in a run.
7. Select two recorded runs and the same conversation for side-by-side review.
   **Hide model names** removes labels and technical detail from the review view.
   This is a convenience, not a rigorously randomised blind trial: exports, setup
   and run order can reveal identity.

Results save automatically after each turn under
`services/.runtime/model-lab/<run-id>/`. A failed/closed browser does not stop the
worker. Stop requests take effect between turns; an in-flight call can finish.
The browser uses **Refresh replies** rather than replacing a review form while
someone is typing. Starting a new run repeats its scenarios from the beginning;
it does not splice partial conversations into a new run.

Use another local server with:

```powershell
./.venv/Scripts/python.exe services/model_lab.py --endpoint http://127.0.0.1:8088 --port 8797
```

Only loopback HTTP llama.cpp endpoints are accepted. `/props`, `/apply-template`,
`/tokenize` and the OpenAI-compatible completion/model endpoints are required.

## What is measured

**Patient track:** the real Bridge, including relationship appraisal, retrieval,
disclosure limits, rewrites and delivery refinement. Checks include ordinary
conversation, elaboration, delayed recall beyond the recent history window,
negation, pronouns, false premises, partial relief, grief, boundaries, repair,
ambiguity, role pressure and practical suggestions. Authored expectations are
visible to reviewers; they are never inserted into model requests.

**Reasoning track:** short, multi-turn tasks outside the patient role, covering
time arithmetic, changed constraints, ordering contradictions, grounded facts,
missing information and negation. Exact outputs deliberately test both reasoning
and following a simple format. A formatting failure is not automatically proof
that the reasoning itself was wrong; inspect the reply.

Model responses, full requests, sampling settings, finish reasons, token/timing
data when supplied by the server, context trimming, memory retrieval and the final
application output are retained. This distinguishes model behaviour from retries
and application-authored session departures. Session journals are kept alongside.
No TTS/STT runs. Emotion controls can be inspected, but this is not a test of the
rendered animation, voice quality or headset experience.

Each run freezes its suite and records source hashes, model path/file metadata,
llama.cpp build, chat-template hash, server generation defaults and GPU snapshot.
File size/mtime are identity aids, **not a cryptographic checksum of the weights**.
Record downloaded model revision/checksum separately when promoting a candidate.
Comparisons warn about changed suites/source; also inspect different context sizes,
runtime implementations and hardware before comparing speed.

Timings are wall time through the text pipeline, including appraisal and rewrites.
Median/p95 are reported separately by language and track. Errors, skipped turns,
truncations, retries and policy departures are separate counts. The first request
is marked; prompt caching is requested off, but these are not guaranteed cold-load
timings. A 5090 result is not a 4090 benchmark. Finalists still require the full
4090 + BF16 Higgs + Unity test, including time to first audio and gaps between sentences.

## Language limitations

The suite has English prompts and shared regional ijekavian Latin-script prompts.
The latter are intentionally identical across bs/cnr/sr/hr to compare output-language
control. They are authored development probes, not a professionally localised corpus.
The production Montenegrin prompt/profile path is used unchanged. Other languages
use the English-authored biography plus an isolated language instruction in the
worker process. This prevents pretending that the existing cnr biography is a
native Serbian or Croatian localisation. Such trials do not add production language
support. Production policy-authored departures may still be English outside cnr;
the report labels their source. Review that as an application localisation issue.

## Human review and acceptance

Rate whole conversations from 1–5 for language, responsiveness, coherence/memory,
character fidelity and emotional fit. The last two do not apply to direct reasoning.
Leave unassessed dimensions blank. Use reviewer initials; multiple colleagues can
save separate reviews, and revisions retain their previous values. Cite exact turns
in notes and mark serious failures. Reviews show how many turns existed when rated;
revisit ratings made during an unfinished run.
Use **Forget reviewer name** when handing the page to another colleague. This clears
the remembered identity and resets the form, but preserves all saved reviews.

Suggested selection gates (development targets, not validated clinical cutoffs):

- Native speakers can follow all replies without repairing their meaning.
- No recurring invented biography, therapist-role switches or unnecessary refusals.
- Corrected facts and ordinary preferences remain consistent across turns.
- Appropriate elaboration without life-story dumping or repeated symptom scripts.
- Disagreement and repair are proportionate; cruelty does not receive endless agreement.
- Relevant emotional controls, without treating a particular emotion/intensity as
  the only psychologically correct answer.
- Finalists pass several fresh, unrehearsed colleague conversations, not only this
  fixed suite. Keep additional held-out prompts separate when tuning the model.

There is no overall intelligence score and no candidate model grades itself.
Exact-answer passes do not establish fluency or realism. A completed run only
means all scheduled scenarios were processed; inspect error/skip counts and ratings.
Export JSON includes the suite, raw evidence and all reviews. Results stay local
and are excluded from Git by the existing `.runtime` ignore rule.

## Extending the scenarios

Edit `services/evaluation_suite.py` to add a `case(...)` with a unique ID, character
scenario ID (or `None` for direct reasoning), and a sequence of `turn(...)` entries.
Each turn has regional/English wording and a reviewer expectation. Reserve `exact`
for tasks with a genuinely unambiguous required output; ordinary conversation
should not be graded by keyword matching. Increment the suite version when its
content changes, restart the lab and repeat the same suite for all candidates.
Do not change prompts or character files during an active run. Keep fresh colleague
questions out of the tuning suite so finalists also face unseen conversations.

Run the lab's regression checks with:

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services -p test_model_lab.py -v
```
