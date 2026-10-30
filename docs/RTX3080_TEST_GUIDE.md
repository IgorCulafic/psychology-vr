# RTX 3080 performance test kit

This kit measures Psychology VR on an RTX 3080 **10 GB or 12 GB**. It preserves the current primary model and `services/config.local.json`. Montenegrin dialogue, the assigned cloned speakers and CPU multilingual transcription are the test context. QAT Q4 dialogue and NF4 speech are explicitly labelled alternatives with quality tradeoffs.

It is a small **overlay for the complete application**, not a standalone application or a model download. It includes the v0.5.3 latency service updates and recorded-speech tools. The game, Python, cloned-voice references, Higgs/Whisper weights and GGUF weights must already be installed. There is no automatic download or upload.

## Run it

1. Close Psychology VR. Run `Stop Services.cmd` in your existing application.
2. Extract the ZIP and merge the contents of its `PsychologyVR` folder into the application folder. Accept replacements of the included service/tool files. Your local configuration is not included in the ZIP.
3. Double-click **`Test RTX 3080.cmd`**. Choose **1** for the quick test.
4. Read `REPORT.txt` in the timestamped folder printed by the test. All results are under `services/.runtime/rtx3080-tests/`.

Use the updated service/tool files together. A typical first quick run can take several minutes; model loading is measured separately. The slow CPU-dialogue combined test can take 10 minutes or more. Do not run two test kits at once. No administrator rights are normally needed; the CMD uses execution-policy bypass for this invocation only.

Missing optional model assets are reported as **skipped**, not silently replaced. Install the optional Gemma QAT Q4 through `PC Settings.cmd` option 6 if needed. Keep the original Q8 weights installed for the Q8 comparison. This runner never applies an optimization-menu profile to the active application.

### Menu

| Option | Measurement | What it answers |
| --- | --- | --- |
| 1 | Quick: QAT dialogue, BF16 voice, CPU STT, **one stage at a time** | Which stage is slow on this PC? |
| 2 | QAT dialogue: 256/128 batch + 8 threads, 128/64 batch + 8 threads, 256/128 batch + 4 threads | Does a smaller batch or CPU pool help this PC? |
| 3 | BF16 cloned voice only, four characters, two passes | First reference use, warm synthesis, RTF and CUDA allocation |
| 4 | BF16 decoder baseline/adapter A/B | Is the optional adapter faster, and are the tested WAV hashes identical? |
| 5 | CPU INT8 multilingual Whisper, beam 5 vs 1, alternating order | Is the small speed gain acceptable for the transcript? |
| 6 | Q8 dialogue only, partial GPU offload | What is the primary model's cost on a smaller GPU? |
| 7 | BF16 voice on GPU + QAT dialogue on CPU + CPU STT + Rhubarb | Functional diagnostic of the quality-preserving combination; expected to be slow |
| 8 | **Experimental** NF4 voice + partial-GPU QAT dialogue + CPU STT | Can smaller voice weights improve combined latency without unacceptable voice changes? |
| 9 | Hardware and dependency inventory | GPU capacity, driver/runtime versions, RAM and installed model presence |
| 10 | GPU/CPU/RAM monitoring during your own running game | Does the real workload hit memory, power or thermal limits? |

Option 8 deliberately opts into quantized speech. The command-line version also requires `-AllowQuantizedVoice`. It is not an approved voice-quality preset. Listen to all four characters and reject it if identity, emotion, stability or Montenegrin pronunciation degrades.

From PowerShell, in the application folder:

```powershell
& .\tools\test-rtx3080.ps1 -Mode quick
& .\tools\test-rtx3080.ps1 -Mode tuning -Turns 8
& .\tools\test-rtx3080.ps1 -Mode voice-ab -Repeats 2
& .\tools\test-rtx3080.ps1 -Mode stt -Audio 'C:\test-audio\montenegrin.wav'
& .\tools\test-rtx3080.ps1 -Mode combined-nf4 -AllowQuantizedVoice -Turns 8
& .\tools\test-rtx3080.ps1 -Mode combined-nf4 -AllowQuantizedVoice -GpuLayers 20
& .\tools\test-rtx3080.ps1 -Mode monitor -Seconds 600
```

An optional STT/combined input WAV must be mono PCM16, 0.2–45 seconds. Use a real Montenegrin microphone recording for a useful recognition test. Without one, STT uses an exact approved Alex recording from the bundled bank; this is a controlled fixture, not an assessment of microphone/noise performance.

For combined conversational-quality testing, supply a recording of a therapist question. The stock Alex fixture contains a patient's statement and only exercises the recognition-to-reply pipeline; it is not a clinical dialogue-quality test.

## Reading the files

| File | Contents |
| --- | --- |
| `REPORT.txt` | Human summary, completion/skips/failures and interpretation |
| `report.json` | All stage results, hardware summary and configuration-preservation check |
| `summary.csv` | Median/p90/maximum where applicable; STT per-beam results are in its stage report |
| `hardware.json` | GPU, CPU/RAM, driver, dependency versions and installed-model presence |
| `gpu-telemetry.jsonl` | GPU 0 VRAM, utilization, temperature, power, clocks and state; Windows process dedicated/shared allocation plus CPU/RAM samples |
| `*/test-config.json` | Exact scoped settings used for that stage |
| `*/worker.log`, `*/llama-server.log`, `*/higgs-server.log` | Model loading, retries, errors and offload details |
| `bf16/wavs/` | The four voices' generated test WAVs, first and warm passes |
| `manual-game-timings.csv` | Blank 20-turn sheet for release-to-audible timing and later gaps |

GPU sampling is approximately every 2 seconds; Windows counters approximately every 10 seconds. Sampling itself adds some CPU work and can miss short peaks. CUDA peak allocated/reserved figures in voice reports help fill that gap. Unsupported counters are marked unavailable. Windows process memory sums across adapters, whereas `nvidia-smi` targets GPU 0. Shared allocation is evidence to investigate, not proof that a tensor was paged or that paging caused a slowdown.

**A completed test is not a 14-second pass.** Dialogue timing excludes STT/speech; voice timing excludes dialogue/STT; combined timing ends at prepared WAVs, with predicted later preparation gaps. Microphone endpointing, network/download delay and actual game/speaker playback are excluded. Do not add separate-stage medians to predict combined latency: concurrency, memory pressure, retries and longer answers change it.

The dialogue test uses the real appraisal and dialogue flow with fixed synthetic prompts, seed 42 and sequential Alex history. It reports the first request after model load separately from later requests. Voice tests retain assigned references/seeds and label first reference use versus warm passes. Detailed replies keep their separate disclosure budget, so some answers may exceed the ordinary 18-word target. Results from different models can have different generated content; compare token rates, word counts, retries and language quality as well as wall time.

## Validation of this download

The new kit ran on the available **i9-14900K / 32 GB / RTX 3080 10 GB**. These are short screening tests; the 12 GB variant has not been measured. Detailed values are saved in `docs/benchmarks/2026-10-17-rtx3080-test-kit.json`.

| New test | Result |
| --- | --- |
| Quick QAT Q4 dialogue | Four turns completed; warm median **3.681 s**, maximum **4.019 s** |
| BF16 cloned voice, sentence mode + decoder adapter | Eight clips completed; four warm clips median **4.233 s**, warm maximum **4.583 s**; first Alex sample **8.288 s** |
| CPU transcription | Beam 1 median **3.042 s** versus beam 5 **3.301 s**; all four transcripts matched the selected stock recording |
| Dialogue tuning, separate four-turn runs | Warm medians: 8 threads / 256 batch **3.533 s**, 8 threads / 128 batch **3.871 s**, 4 threads / 256 batch **3.455 s** |
| Optional NF4 combined, 16 GPU layers | First prepared reply **31.955 s** including STT; next turn failed speech validation after **88.881 s**. The requested four-turn run did not complete. |

The small 4-thread gain is insufficient to establish a universal winner; the smaller batch was slower here. Keep the default baseline until a repeatable improvement appears on your PC with the game running.

The NF4 run loaded speech at about **3,539 MiB** allocated, but most dialogue blocks remained on CPU. Its first reply's appraisal and dialogue took about 24 seconds together. A later speech decode reached its 900-frame limit twice without a normal stop; the generated audio was rejected. **This tested NF4 configuration is not a working 14-second preset.** Its menu entry remains available for diagnosis and controlled comparisons, with explicit voice-quality opt-in. Lower memory alone does not ensure lower latency or valid speech.

All test runs preserved the active local configuration and cleaned up their model services. The automated tests cover ownership, both health-response formats and visible partial results after a failed later turn. Audible game timing and native Montenegrin review remain manual acceptance checks.

## Earlier measured starting point on our available RTX 3080

These are **previous measured results from 17 October 2026**, not predictions for your PC or for a 12 GB card. Hardware: i9-14900K, 32 GB system RAM, RTX 3080 10 GB, driver 617.14. Source: `docs/benchmarks/2026-10-17-latency-audit.json` and `docs/RTX4090_LATENCY_AUDIT.md`. New test results are saved separately and can differ because of the revised reply budget and sentence settings.

| Workload | Measured time / observation | Scope |
| --- | --- | --- |
| Q8, GPU-layer setting 32 | Warm median **21.495 s** | Appraisal + dialogue; no voice/STT/game |
| Q8, GPU-layer setting 36 | Warm median **21.413 s**; cold **38.286 s** | More offload did not give a useful warm improvement in that test |
| QAT Q4, full GPU offload | Warm median **3.486 s** | Dialogue-only alternative; different precision and potentially different answers |
| Warm BF16 cloned speech | Roughly **2.9–4.6 s** for the selected 2.88–4.88 s clips | Voice alone; not representative of arbitrarily long replies |
| BF16 speech allocation | About **8,546 MiB** resident; roughly **9,305 MiB** observed allocated peak | Most of a 10 GB card before game/dialogue memory |
| CPU Whisper large-v3-turbo | Beam 5 median **3.066 s**; beam 1 **2.983 s** | Short controlled clips; recognition still needs review |
| QAT dialogue on CPU + BF16 GPU speech | First-prepared median **58.880 s**, four voices | Combined functional diagnostic; clearly failed 14 s |
| Combined Windows memory snapshot | Speech process ~9,019 MiB dedicated + ~1,806 MiB shared | Allocation observed; exact paging cause not proved |

The optional BF16 decoder adapter had small, variable gains: around 0–4% on these short clips, with one voice slightly slower. Eight matched pairs produced identical WAV hashes. This is sample parity, not a guarantee for all future text. It cannot account for a 20-second improvement by itself.

### What 10 GB versus 12 GB changes

| Configuration | 3080 10 GB | 3080 12 GB |
| --- | --- | --- |
| QAT Q4 dialogue alone | Measured, fast on this machine | Test kit supported; not locally measured |
| BF16 cloned speech alone | Measured, very little headroom | More headroom; no measured speed guarantee |
| Full QAT GPU dialogue + BF16 speech together | Exceeds practical capacity | Also exceeds practical capacity |
| Q8 full GPU + BF16 speech | Unsuitable for this capacity | Unsuitable for this capacity |
| NF4 speech + partial GPU QAT dialogue | Optional comparison starts at setting 16 | Optional comparison starts at setting 24 |
| Q8 dialogue-only comparison | Starts at setting 20 | Starts at setting 28 |

The last two rows are conservative **starting experiments, not proven best layer counts or fit guarantees**. This kit skips heavy tests if free dedicated memory is below its screening threshold (about 9,500 MiB for BF16 voice, 8,000 MiB for the other GPU tests). These thresholds are approximate, assume the installed model versions, and do not reserve game memory. Close other GPU applications before retrying; a skip is not a claim that the GPU cannot execute that stage.

For an offload sweep, use `-GpuLayers` in dialogue or NF4 combined mode. Compare the default first, then try a small increase (for example 16 to 20 in the 10 GB NF4 test). Stop raising it if loading fails, shared allocation grows with latency, or dedicated headroom disappears. The kit does not automatically search for the largest allocation. The BF16 combined diagnostic keeps dialogue on CPU and rejects this override.

Bundled llama.cpp b10909 counts the output layer among GPU layers: setting 32 offloads 31 of Gemma's 48 transformer blocks plus the output; setting 36 offloads 35 blocks plus the output. Full offload is 49 eligible layers; 99 requests all. Do not interpret a partial setting as a percentage of GPU usage or blindly set 99 for combined speech.

## Tweaks, in useful order

| Tweak | How to evaluate / limitation |
| --- | --- |
| Reduce simultaneous model VRAM | The largest issue. Run QAT dialogue alone first, then voice alone, then a deliberate combined profile. More system RAM does not replace dedicated GPU bandwidth. |
| Optional QAT Q4 dialogue | Biggest measured dialogue gain here. Compare Montenegrin wording, character consistency and detail quality against Q8 before selecting it for use. The primary Q8 installation is preserved. |
| Keep multilingual STT on CPU INT8 | Leaves VRAM for dialogue/speech. Beam 1 has only a small measured gain; inspect transcript accuracy. Never use `small.en` for this Montenegrin test. Optional multilingual small/medium models need installation and a fresh accuracy comparison. |
| Ordinary short replies + meaningful first sentence | Current test template targets 18 ordinary words; fuller answers keep their separate budget. Reduces generated tokens and voice work; listen for naturalness. Avoid hard audio/text truncation. |
| Sentence delivery | Can make the first prepared part available sooner. Later parts can still stall; compare the longest extra gap and listen for pacing/prosody changes. |
| Flash Attention + Q8 KV + stable prompt caching | Enabled in the test baseline. Q8 KV is a cache precision choice, separate from dialogue weights. Keep enough context; reducing it can lose history or trigger context errors. |
| Batch 256/128 versus 128/64 | Menu 2 tests this with the same model. Smaller batches may reduce scratch memory; speed can improve or worsen. Re-run the candidate in the full game before choosing it. |
| CPU threads 8 versus 4 | Menu 2 tests it. Higher total CPU utilization does not prove higher token throughput. Reserve headroom for STT/game; avoid blindly using all logical cores. |
| GPU-layer sweep | Adjust a COPY of the test template and use the Python `--config` option for deliberate experiments. Raise layers gradually only when dedicated-memory headroom is measured. On 12 GB, start with kit defaults rather than assuming 4090 settings fit. |
| BF16 decoder adapter | Menu 4 checks speed and output parity on fixed samples. Expected gain is small and variable. Preserve the pinned model source. |
| Release unused CUDA cache | Enabled in the voice test. Returns unused allocator blocks, not resident weights; may add allocation overhead. Test with/without using a copied template. |
| Optional NF4 / INT8 cloned voice | NF4 combined comparison is menu 8. INT8 can be tried only in a copied test configuration with explicit `higgs_allow_quantized_cast: true`; less memory reduction than NF4. Both require fresh voice/pronunciation approval and may be slower on some kernels. |
| Exact recordings and generated-speech cache | Useful for repeated approved lines; cannot supply arbitrary new replies. Caches are deliberately disabled during fresh-generation benchmarks. Cache-hit timing must be reported separately. |
| Lip sync: Rhubarb versus audio envelope | Envelope animation can remove alignment work but changes mouth quality. Use the existing optimization menu option 9 only as a conscious application setting change; compare actual game behavior. |
| MTP speculation | Requires the matching Q8 draft and extra memory; no matching QAT draft is configured. On an already full 3080, it is a separate experiment, not a default fix. |
| Reduce desktop/VR render memory | Close unrelated GPU workloads, reduce game resolution/texture/MSAA cost where supported, test desktop first, then VR separately. The automated isolated tests do not measure game FPS. |
| Clocks, power and thermals | Inspect telemetry for repeatable clock drops, rising temperatures or power limits. Use normal supported settings and cooling; no overclock/BIOS/registry changes are applied by this kit. |
| Driver / HAGS / power preferences | Treat as controlled A/B experiments only if a symptom points there. Record the baseline and change one thing at a time; no universal latency improvement is claimed. |
| More GPU capacity / separate inference device | If BF16 voice and current dialogue quality are mandatory together, moving one service to another GPU/host or using more VRAM is a practical architectural option. Deployment/device routing still needs setup; this kit does not implement it. |
| Smaller approved dialogue or voice model | Another route to fit. Needs Montenegrin capability and speaker-quality evaluation; an English-only voice replacement does not satisfy this project. |

Do not disable the Windows page file, force unsupported driver memory-fallback settings, change global CPU affinity, or apply CUDA allocator flags as an assumed fix. The kit makes no such changes. A smaller context/KV format, extra GPU layers or quantized speech should be accepted only after a measured comparison with language/voice quality checks.

## Decide whether the 14-second goal is met

1. Choose a candidate only after standalone tests and one combined run finish without errors or large memory spill.
2. Launch the desktop application with that candidate deliberately applied; the kit itself leaves your active configuration unchanged.
3. Run monitor mode while testing **20 new turns** across Alex, Ivan, Stefan and Nikola. Include short questions, a request for detail, one interruption and a longer conversation. Test VR separately if needed.
4. From an audio/video recording, measure **end of user speaking to first audible response**, then the longest unintentional silence between response parts. Fill `manual-game-timings.csv`. Keep deliberate emotional pauses separate.
5. Report cold first response, warm median, p90, maximum, failure count and later gaps. To claim every measured answer meets 14 s, **every included turn must be at or below 14 s**; a median below 14 is insufficient. Repeat after any quality-affecting change.

Neither the prior tests nor this download proves a 14-second audible result on a 3080 or 4090. The 4090 was unavailable. A four-turn screening run is too small to certify stable performance or native Montenegrin quality.

## Test coverage and remaining gaps

| Area | Test type / target | Example |
| --- | --- | --- |
| Current settings and speaker precision | Automated unit tests; all scoped profile paths must preserve the input template | Ordinary BF16 stays BF16; NF4 requires explicit opt-in |
| Process ownership | Real subprocess smoke test and socket integration test | Inject an error; owned worker stops, occupied unrelated listener remains alive |
| Failure/report integrity | Unit tests + local hardware run; failures must remain visible | Existing service blocks the run; partial reports remain readable; no false 14 s success |
| Model inference / voice / STT | Real GPU integration on available 10 GB hardware | Cold/warm timings, token metrics, sample WAVs and alternating STT beams |
| Actual release-to-audible latency | Manual 20-turn acceptance test | First audible reply and later gaps from recording |
| Language and identity | Native listener review required | Listen to four speakers, compare NF4/BF16 and transcript errors |

Unverified gaps: RTX 3080 12 GB measurements, your exact game/VR load, native-speaker approval, extended conversation stability, and an audible <=14 s result. The optional combined NF4 configuration is experimental until tested on the intended installation.

Technical references: [bundled llama.cpp build/backend documentation](https://github.com/ggml-org/llama.cpp/blob/b10909/docs/build.md), [bundled GPU-layer selection implementation](https://github.com/ggml-org/llama.cpp/blob/b10909/src/llama-model.cpp), [faster-whisper CPU/quantization documentation](https://github.com/SYSTRAN/faster-whisper), and [PyTorch CUDA memory management](https://pytorch.org/docs/stable/notes/cuda.html#memory-management). Model/runtime compatibility should be checked against the installed versions rather than upgrading all dependencies during a performance comparison.
