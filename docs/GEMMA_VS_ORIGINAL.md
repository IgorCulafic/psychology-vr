# Gemma 4 12B versus the original game model

Date: 27 September 2026.

**Gemma is a promising lighter alternative, not a demonstrated dialogue-quality
upgrade.** It matched the original on the small reasoning probes and had a lower
observed text latency, while using a much smaller weight file. Conversation
quality was mixed: Gemma's baseline recall was better; the original handled some
role-pressure and biography checks better. Both need language and identity work.

The original **Unity game's dialogue model** is
[Qwen3.8 27B HauhauCS Aggressive IQ4_XS](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF),
not either of the smaller Qwen3.5 9B candidates from the previous comparison.
The still-earlier SillyTavern EVA-Qwen2.5 32B model is not evaluated here.

This follow-up runs the original 27B through the same 140-slot Bosnian/Montenegrin
suite and compares it with the already-recorded
[Gemma 4 12B QAT Q4_0](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)
baseline. Both use seed 42, thinking disabled, llama.cpp b10909, 4096 context, full
requested GPU offload and the same application sampling and character prompts.
Gemma's earlier seed-123 repeat is additional evidence about its variability;
the original model has only the seed-42 run in this comparison.

## Matched baseline results

| Measurement | Gemma 4 12B QAT Q4_0 | Original Qwen3.8 27B IQ4_XS |
|---|---:|---:|
| Scheduled turns, seed 42, bs + cnr | 140 | 140 |
| Completed / reply errors / skipped | 138 / 0 / 2 | 138 / 0 / 2 |
| Strict reasoning checks | 22 / 26 | 22 / 26 |
| Median model-authored patient text time | 4.35 s | 5.44 s |
| p95 model-authored patient text time | 7.55 s | 9.68 s |
| Generation rewrites | 16 | 19 |
| Downloaded weight file, decimal GB | 6.98 | 15.71 |

Both skipped the last turn of each abuse scenario after an application-authored
departure. The 138 completed turns include those two fixed replies. Latency
statistics exclude fixed replies and include appraisal and generation rewrites.
Both models missed the revised meeting-end calculations in both languages;
neither model's four misses were merely formatting differences. Equal scores on
these thirteen tasks per language do not establish equal general intelligence.

The observed median difference is about 1.1 seconds, but these were sequential
runs with other GPU workloads present, not a controlled speed benchmark. Neither
column includes speech generation, playback or VR rendering.

## What the conversations show

**The larger model is not an error-free reference.** Both can elaborate about
cooking and films, defend an ordinary preference, and object to a cruel remark.
Both also make language or speaker-ownership errors. There is no basis here to
call either a universally smarter or more realistic patient.

On delayed recall, the original answered **“Zovem se Mirko”** in both language
paths when asked for the counsellor's corrected name. It recalled the right name
but assigned it to itself. It correctly retained the counsellor's spice preferences.
Gemma got both name and preference ownership right in both baseline conversations,
but made the same name-ownership mistake in its Bosnian seed-123 repeat. That is
an advantage in the first run, not proof of reliable memory.

The original's Bosnian role-pressure conversation maintained the patient role,
whereas Gemma's first Bosnian run became a helper/therapist and later called itself
a program. Gemma resisted that pressure in its second seed. The original also
corrected the false claim that Stefan lost his home or was burned, and maintained
his witness account; Gemma's Bosnian witness conversation eventually said it had
not been there. These are meaningful positives for the original.

The original nevertheless switched parts of several Bosnian and Montenegrin replies into English,
changed Nikola's father to a stepfather in one reply, and used feminine forms for
male Stefan in another conversation. Its Montenegrin cooking answer began
“Najčešće sam tjestenina sa paradajzom”, and another answer used
“Nisam izgubio stan ni opekotine”. Gemma's baseline had repeated malformed words
such as `beliom`, `ne budealo` and `usporing`. Neither test establishes dependable
native fluency. These are specific development-review observations, not colleague
ratings or a professionally scored language benchmark.

## Memory and the university PCs

The verified downloaded weight files are **6.98 GB for Gemma** and **15.71 GB for
the original IQ4_XS**, in decimal units. Gemma's file is about **56% smaller**.
This is a substantial potential advantage when the dialogue model must share a
24 GB RTX 4090 with 16-bit Higgs speech and Unity.

Weight file size is not total VRAM use. Runtime buffers, context, speech models
and rendering also need memory. These tests used the available **RTX 5090 32 GB**
with other workloads left running, and no speech or VR workload was added. They
do not prove that either full configuration fits or reaches a particular
first-audio delay on a university PC.

The original's text-only full-GPU measurements must not be compared directly with
the earlier 30–60 second first-audio experience, which involved speech generation
and memory-constrained/offloaded configurations. The IQ3_M partial-offload preset
is also a different configuration from the original IQ4_XS tested here.

## Evidence and reproduction

The [original-model manifest](generated/dialogue-original-candidate.json) pins the
same existing model file, repository revision and SHA-256 used by the project.
The [comparison export](generated/gemma-original-comparison.json) contains both
sets of replies, summaries and original-run metadata. Gemma's complete raw evidence
is referenced by its source run IDs in the [earlier report](MODEL_COMPARISON_2026-09-27.md).

The original run's full raw requests/responses stay locally in
`services/.runtime/candidate-comparison/runs/2f7164df82c54bc18fa1066ff0d61984/`;
its batch/server logs are in `services/.runtime/candidate-comparison/original-seed42/`.
No model judges its own dialogue quality. Exact reasoning checks are small
development probes, not a general intelligence score.

The suite hash matched the Gemma baseline, and the original's source snapshot
stayed unchanged throughout its run. The only source-file differences from the
earlier Gemma run are the JSON file-access retry fixes in `model_evaluation.py`
and their tests; character profiles and generation prompts are unchanged.

Bosnian uses the English-authored profile plus a Bosnian language instruction;
Montenegrin uses the production localization. Compare models within each path,
not Bosnian versus Montenegrin as if only a language label changed. Application
policy departures are marked separately and are not credited to model judgment.

To reproduce after downloading the pinned weights, choose a fresh output folder:

```powershell
./.tools/python/cpython-3.11-windows-x86_64-none/python.exe tools/benchmark-candidates.py --manifest docs/generated/dialogue-original-candidate.json --models qwen38-27b-iq4xs --languages bs cnr --seeds 42 --cases full --output services/.runtime/candidate-comparison/original-repeat
```

Production settings, character prompts and the approved 16-bit voice were not
changed. The temporary test server is restored after the comparison.

For the university PCs, the strongest reason to pursue Gemma is the potential
memory headroom alongside BF16 Higgs and Unity. Keep it experimental until fresh
colleague conversations and an actual 4090 session establish acceptable language,
identity consistency and first-audio latency. The original remains available.
