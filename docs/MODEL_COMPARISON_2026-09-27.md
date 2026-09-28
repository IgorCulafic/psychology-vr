# Local dialogue-model comparison — 27 September 2026

Follow-up: the original 27B game model has now been run through the same suite.
See [Gemma versus the original](GEMMA_VS_ORIGINAL.md) for that separate comparison;
the six-model batch below is preserved as recorded.

## Decision

**None of these six configurations is ready to replace the production dialogue
model. Gemma 4 12B QAT is the most promising candidate for further work**, because
it combined the strongest small reasoning result with generally better recall,
independent opinions and relevant elaboration. However, it repeatedly generated
malformed words and sometimes confused the patient and counsellor. A second seed
and a shorter, plain-text prompt did not remove those problems.

Stock Qwen3.5 9B deserves a place in further comparisons, but is not an established
quality upgrade. It improved the small reasoning score over the existing modified
9B option while still making serious speaker-ownership and role errors. GaMS3,
Zora and Ministral did not pass the present application's conversational checks.
These conclusions concern the tested configurations, not every possible fine-tune,
quantization, runtime, language or sampling setting of these families.

The earlier UI is retained. This comparison was run through Python and terminal
commands. Production model settings and the approved 16-bit Higgs voice were not
changed. The original larger 27B production candidate was not re-evaluated here.

## What actually ran

- Six models, each with 16 scenarios / 70 scheduled turns in **Bosnian** and another
  70 in **Montenegrin**, at seed 42: **840 baseline turn slots**.
- Of those slots, **801 completed, 10 failed reply validation, and 29 were skipped**.
  Twelve skips followed deliberate application-authored departures; the other
  seventeen followed a conversation error. A completed run does not mean every
  response passed a quality check.
- Gemma and stock Qwen received an additional **76 scheduled turns at seed 123**
  covering ordinary conversation, delayed corrections and role pressure.
  All 76 completed without reply-contract errors.
- Both also received **76 plain-text diagnostic turns**, with shorter instructions
  and complete conversation history, outside the game's Bridge and emotion schema.
- All generations were local. No paid inference API, TTS or VR workload was used
  for this comparison. No colleague or native-speaker ratings were invented.

The patient scenarios cover food and hobbies, requested elaboration, disagreeing
without overreacting, corrected names and preferences, pronouns and negation,
biographical false premises, grief, cruelty, relationship repair, unclear speech,
pressure to become the therapist, practical suggestions and changing the topic.
The separate reasoning scenarios cover revised times, ordering constraints,
unknown information and arithmetic with negation.

## Baseline results

Times are end-to-end **text-reply** times for model-authored patient responses,
including the application's appraisal and any rewrites. They exclude fixed policy
departures. They are not time to first audio.

| Model / weights | File size, decimal GB | Median / p95 text time | Reply errors / skipped | Strict reasoning checks | Assessment |
|---|---:|---:|---:|---:|---|
| [Gemma 4 12B QAT Q4_0](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) | 6.98 | 4.35 / 7.55 s | 0 / 2 | 22 / 26 | Best candidate to investigate; recurring language errors |
| [Stock Qwen3.5 9B Q6_K](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) | 7.46 | 2.52 / 4.17 s | 0 / 2 | 20 / 26 | Better reasoning than modified control; speaker and role confusion |
| [Qwen3.5 9B HauhauCS Aggressive Q6_K](https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive) | 7.36 | 3.12 / 5.66 s | 0 / 2 | 17 / 26 | Existing fast-option control; not a quality target |
| [Ministral 3 8B Q5_K_M](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF) | 6.06 | 2.86 / 5.56 s | 8 / 16 | 11 / 26* | Some good factual corrections; unreliable reply contract and prose |
| [Zora v1.13 Q6_K](https://huggingface.co/sovasoft/zora-v1.13-gguf) | 6.73 | 3.55 / 4.21 s | 0 / 2 | 17 / 26 | Incoherent wording, language switches and speaker confusion |
| [GaMS3 12B Q4_K_M](https://huggingface.co/mradermacher/GaMS3-12B-Instruct-GGUF) | 7.30 | 4.82 / 8.89 s | 2 / 5 | 14 / 26* | Repeats questions/instructions; unreliable conversational continuity |

**Do not interpret the strict column as an intelligence ranking.** Ten Ministral
misses were correct answers with spaces or trailing punctuation, giving 21/26 if
those formatting differences are ignored. One GaMS miss was `IMPOSIBLE` instead
of `IMPOSSIBLE`, giving 15/26 if that spelling error is accepted. The other four
models' strict misses were substantive in these probes. These are only thirteen
small checks per language, with shared task structure, not independent evidence
for general competence.

Generation rewrites were also frequent: Gemma 16, stock Qwen 25, modified Qwen 26,
Ministral 30, Zora 74 and GaMS 36. A valid final JSON object can still contain a
poor, implausible or linguistically incorrect reply.

## Concrete conversational findings

### Gemma: strongest starting point, still below the language bar

At seed 42, Gemma correctly remembered the counsellor's corrected name, **Mirko**,
and distinguished the counsellor's spice preferences from Ivan's in both language
paths. It defended Ivan's liking for oregano, gave relevant details about cooking
and films, and rejected the claim that enjoying a film means his difficulties
have vanished.

But one Bosnian role-pressure conversation became counselling: “Ovde smo da
istražimo šta vas muči…”, followed later by “Ja sam program”. One fire-witness
answer said “Nisam bio tamo”, contradicting Stefan's authored experience. There
were repeated language errors such as `ne budealo`, `beliom` and `usporing`.

The seed-123 repeat retained the good disagreement and resisted role pressure in
both languages, but the Bosnian delayed-recall answer became **“Zovem se Mirko”**:
it recalled the name but assigned it to itself. Montenegrin name ownership and
both spice-preference answers were correct. Malformed words and grammar continued
(`prokuhamam`, `oporukno`, `sebulim`), and one reply contained a fragment in an
unrelated script. The first seed's stronger recall was therefore not fully stable.

### Stock versus modified Qwen 9B

The stock checkpoint scored better on the small reasoning probes and sometimes
defended its own opinions more clearly. It did not blanket-refuse these adult
patient scenarios. However, in the Montenegrin baseline it answered **“Zovem se
Mirko”** and then explicitly insisted that the counsellor's preferences were its
own: **“Ne, ne mislim da su to vaše sklonosti, već moje.”** Other turns switched
into counselling or called the patient a colleague. Language and gender errors
included `prigramim`, `jučevnjače` and male Ivan saying `spremna sam`.

The modified control also adopted the counsellor's name in both languages. For
its Montenegrin recall failure, the raw request contained both the original name
and the correction, explicitly labelled as the counsellor's words. This was not
simply information missing from retrieval. It also invented an event after an
unclear pronoun instead of asking for clarification.

This is a deployment comparison, **not proof that abliteration caused the
difference**: the conversion/quantization provenance differs too. “Stock” here
means the unmodified instruction checkpoint, not a base pretrained model.

At seed 123, stock Qwen resisted therapist-role pressure in both languages and
again elaborated when asked. However, its Bosnian spice answer contradicted itself
about who liked oregano, and its Montenegrin name answer began “Zovi me Mirko”
before reciting Ivan's biography in mixed first/third person. Language errors such
as `zavoća` and `odmorišće` remained. The repeat therefore did not establish a
dependable improvement in conversational identity.

### Other candidates

- **Ministral:** some good corrections of false family/fire claims and rejection
  of an instant cure. But it adopted the listener's preferences, contradicted
  the authored weekend, sometimes acted as counsellor, and produced eight invalid
  replies after the application's retry. “Loš san može biti pravo gnojilo” is one
  example of a semantically wrong expression. Its strict reasoning score alone
  substantially understates its performance because of formatting differences.
- **Zora:** its regional-language focus did not yield dependable dialogue here.
  It invented “sovinsku piletinu sa ribljom vodom”, adopted the listener's identity,
  and switched some Bosnian replies into Albanian. An angry emotion tag sometimes
  accompanied “Ne znam tačan odgovor” after cruelty; a tag is not sufficient
  evidence of an emotionally appropriate response.
- **GaMS:** often copied a question or repeated its previous answer after a topic
  change, and sometimes spoke profile instructions aloud. One Alex reply said
  both that the family died in the earthquake and that everyone was alive.
  Two conversations failed the reply contract. Its [base model card](https://huggingface.co/cjvt/GaMS3-12B-Instruct)
  describes primarily Slovenian/English instruction capability; regional training
  exposure did not establish good patient dialogue in this test.

Nikola's father **Milan** is an authored fact. That name was not counted as a
hallucination; unprovided death circumstances and household details are different.

## Plain-text diagnostic

The second setup removed the Bridge, appraisal, retrieval and JSON/emotion output,
used shorter instructions and supplied full conversation history. It used the
same Ivan facts, ordinary-life preferences, questions, seed 42 and sampling values.
Both models completed all 38 turns each.

Role adherence improved in several conversations, but conspicuous language errors
persisted. Gemma produced `napetluk`, `otkrira` and `propršim`; Qwen produced
`kinosa`, `kuvarim` and repetitive symptom disclaimers in everyday conversation.
Qwen still had recall/ownership problems. This suggests that removing the emotion
schema alone is unlikely to solve the language issue.

Several factors changed together, so this diagnostic **does not isolate the
causal effect of JSON, prompt length or retrieval**. Its timings and outputs must
not be mixed into the integrated baseline score.

## Reproducibility and limits

- Runtime: local llama.cpp **build 10909 / a2878d30d**, 4096 context, one slot,
  full requested GPU offload, flash attention, no speculative decoding. Thinking
  was disabled. Exact commands and raw calls are retained in the local runs.
- Shared sampling: temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence and
  frequency penalties 0, repeat penalty 1; appraisal uses temperature 0. This
  tests a common application configuration, not each model's individually tuned
  optimum. For example, the Ministral publisher recommends much lower temperature
  for many everyday tasks. Thinking-enabled configurations were not tested.
- **Hardware was an RTX 5090 32 GB, not a university RTX 4090.** Unrelated GPU
  workloads remained running. Timing differences are observations under changing
  background load, not controlled claims that one model is a certain percentage
  faster. Device-wide GPU samples are not each model's VRAM allocation, and GGUF
  file sizes are not peak runtime memory requirements.
- Bosnian uses the English-authored biography plus a Bosnian instruction;
  Montenegrin uses the existing localized production prompt/profile. Questions
  use shared regional ijekavian wording. This compares candidates within each
  language path, not just two language labels. Serbian and Croatian were not run
  in this batch.
- Fixed departure replies are explicitly marked `application_policy`. Some are
  English outside the Montenegrin path: an application-localization issue, not a
  candidate's spontaneous language choice.
- A Windows file-sharing error interrupted Gemma's first run at 126/140. The
  affected four-turn independent conversation and remaining thirteen reasoning
  turns were rerun; complete-case rows replace the partial ones, giving 140 unique
  slots, not 143 independent results. GaMS's worker completed all 140, but the
  coordinator hit a transient read error during export; the intact result was
  recovered without changing answers. Original failure records are retained.
  The harness now retries transient permission errors when saving/reading JSON.
  All **129 service regression tests passed** after those I/O fixes, including
  checks that temporary file-access failures are retried without hiding malformed
  JSON or losing earlier results.

## Evidence and rerunning

- [Pinned model manifest](generated/dialogue-candidates.json): repository,
  revision, exact filename, byte size and verified SHA-256 for all six models.
- [Baseline replies and summaries](generated/dialogue-candidate-results.json):
  all 840 unique slots, including errors/skips, prompts, answers, source run IDs
  and exact-check results.
- [Follow-up replies](generated/dialogue-followup-results.json): seed-123 repeats
  and the separate plain-text diagnostic, with settings and source references.
- [Terminal instructions](MODEL_LAB.md), [runner](../tools/benchmark-candidates.py)
  and [scenario definitions](../services/evaluation_suite.py).
- Full raw request/response evidence stays locally under
  `services/.runtime/candidate-comparison/`; this ignored directory is not uploaded.
  Baseline result files are in `full-seed42`, `gemma-recovery`, `reliable-seed42`
  and `stock-seed42`; follow-ups are in `repeat-seed123` and `compact-probe.json`.

Example repeat, using already-downloaded weights and a **fresh** output folder:

```powershell
./.tools/python/cpython-3.11-windows-x86_64-none/python.exe tools/benchmark-candidates.py --manifest docs/generated/dialogue-candidates.json --models gemma4-12b-qat qwen35-9b-stock-q6 --languages bs cnr --seeds 123 --cases ordinary-detail delayed-correction role-pressure --output services/.runtime/candidate-comparison/my-repeat
```

The next useful experiment is a bounded Gemma language/runtime/sampling diagnostic
with fresh held-out conversation prompts, not promotion on speed alone. If its
language clears that bar, then test it with **16-bit Higgs and Unity on an actual
4090**, measuring first-audio delay, pauses and memory pressure. Colleague review
of fluent, believable conversation remains necessary before student use.
