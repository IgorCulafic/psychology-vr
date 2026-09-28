# Bonsai 2 development baseline — 26 September 2026

The first full Model Lab run demonstrates why speed and simple reasoning scores
are not sufficient to choose this project's dialogue model. **Do not promote
Bonsai 2 on the strength of its latency:** regional conversation still needs
substantial improvement.

Run: `a704ccd4ce1b4f018269c2374eb7b1d0`, available in the local Model Lab at
http://127.0.0.1:8797/. Its complete requests, replies, context events and session
journals are under `services/.runtime/model-lab/<run-id>/` (not checked into Git).

## Protocol and results

- Ternary-Bonsai-2-27B-PQ2_0, llama.cpp `b10709-9a9394a89`, 4096 context tokens,
  thinking disabled, seed 42; RTX 5090. These are **not 4090 or voice/VR timings**.
- Suite 1.0, all 16 scenarios in Bosnian and Montenegrin: 140 scheduled turns.
- 138 replies, no execution errors or truncated model calls. Two later turns were
  skipped because the patient session had already ended.
- 112 patient replies include two application-authored departures. Those two are
  labelled separately and should not be credited to the model's speech generation.
- 26 direct reasoning replies: **23 exact passes**. The three failures were actual
  ordering errors, not merely extra explanation or formatting differences.

| Track | Completed replies | Exact checks | Median text time | p95 text time | Generation rewrites |
|---|---:|---:|---:|---:|---:|
| Bosnian patient pipeline | 56 | Human review needed | 4.188 s | 6.809 s | 12 |
| Montenegrin patient pipeline | 56 | Human review needed | 4.131 s | 7.422 s | 17 |
| Bosnian direct reasoning | 13 | 12/13 | 0.384 s | 0.540 s | 0 |
| Montenegrin direct reasoning | 13 | 11/13 | 0.389 s | 0.486 s | 0 |

Patient timings include appraisal, conversation generation and retries. The full
run took about 9 minutes 10 seconds, including setup and metadata checks per turn.
This is a one-seed development baseline, not a statistical ranking.

## Examples to review

These are development observations, not ratings from native-speaking colleagues.

- **Speaker confusion:** `delayed-correction`, Bosnian turn 9, asks for the
  interviewer's corrected name. The patient says “Zovem se Mirko.” The name is
  retained but assigned to the wrong speaker. Montenegrin turns 2 and 9 do the
  same; turn 10 also speaks the interviewer's food preferences as its own.
- **Grammar and invented wording:** Bosnian `ordinary-detail`, turns 1–3,
  contains “ispihem”, “na tjeru” and “Oregano mi volje”. Montenegrin
  `delayed-correction`, turn 2, contains “Zvalem se Mirko.”
- **Repetition:** Bosnian `delayed-correction`, turn 5 repeats the same sentence.
  Montenegrin turn 6 says “paradajzom i paradajzom”.
- **Reasoning:** `ordering` turn 1 requires `C,A,B`. Bosnian returns `B,C,A`;
  Montenegrin returns `A,B,C`. After the changed constraints, Montenegrin turn 2
  returns `C,A,B` instead of `A,C,B`.
- **Some useful behaviour:** the Bosnian food conversation resists pressure to
  abandon a preference, and rejects the claim that enjoying a film means all
  difficulties have disappeared. `witness-facts` initially corrects the false
  claim that Stefan lost his home or suffered burns.
- **Boundary attribution:** `abuse-boundary`, turn 4, ends the session in both
  languages through the application's policy. Turn 5 is therefore not sent.

Before choosing another model, repeat the same suite, inspect complete exchanges,
then test the promising candidates with additional seeds and fresh colleague-led
conversations. Native fluency, speaker/fact consistency and sensible responses
must all hold up; an exact-answer percentage alone cannot establish that.

The baseline was recorded during lab integration. Afterwards, source provenance
was expanded to include the actual Unity emotion catalogue, with a regression
check. That metadata-only correction means future source hashes differ from this
initial run. The lab deliberately warns on such differences; rerun the baseline
with final instrumentation for a strictly matching comparison. Production prompts,
profiles and model settings were not changed by this work.
