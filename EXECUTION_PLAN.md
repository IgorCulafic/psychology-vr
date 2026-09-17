# Psychology VR — execution plan

Prepared 11 September 2026. Updated after implementation: the Windows desktop prototype has local Qwen dialogue, Kokoro speech, faster-whisper transcription, a furnished consultation room, and a seated character with a shared 20-state emotion catalog, blinking, gaze, timed lip sync, and prototype tear tracks. See [BUILD_STATUS](docs/BUILD_STATUS.md) for verified results. The body revision adds exaggerated IK performances, face-in-hands crying, facial flushing and moving tears. Hand-contact polish, expressive voice, and Quest acceptance testing remain open.

## Target and working assumptions

Build a seated conversation with Alex, a fictional earthquake survivor, in Unity. The player practises a supportive conversation while Alex responds through speech, facial expression, posture, gaze, and hand gestures.

Confirmed target: Meta Quest 3 connected to a Windows PC with an RTX 4090, 64 GB DDR5 RAM, and an i9-14900KF. Unity rendering and local AI services share that PC. Use a cable for the first headset tests. Speech providers remain interchangeable so a free-tier API can be used during development if useful.

Working assumptions: English first; one player, one patient, one session at a time; a quiet consultation room within or associated with the crisis shelter. Alex still lives in temporary accommodation, so the room adaptation preserves his existing history. These assumptions can be revised without changing the architecture.

First playable target: a roughly ten-minute conversation with reliable microphone input, coherent replies, audible speech, visible emotional cues, interruption/reset controls, and stable VR rendering. This is a fictional practice prototype. Formal educational scoring is a separate design task.

## What is in the folder

| Supplied item | Finding | Planned use |
|---|---|---|
| `Character description.txt` | Alex is 35, displaced after an earthquake, has a back injury, fears aftershocks, and has surviving family. Includes an opening and example exchanges. | Source for character facts, dialogue examples, and a scripted opening. |
| `Persona Description.txt` | Describes the player as a psychology student or crisis counsellor aiming to build rapport and support Alex. | Session introduction and player role. It does not guarantee that the actual player will speak empathetically. |
| `Authors note.txt` | Empty. | No behavioural rules to import from this file. Keep the original as supplied. |
| `man/source/dhana.gltf` | One skeleton, 168 joints including control bones, 10 meshes, 9 materials, about 10,952 vertices and 16,737 triangles. Six animation clips. Images are embedded in the glTF. | Candidate for the initial character import and body animation tests. |
| `man/textures/` | Ten supplied texture images. | Retain as source material; avoid importing duplicates unnecessarily. |

Animation names and reported end times: `Action` 2.87 s, `salute` 2.87 s, `sit` 7.03 s, `shakehand` 4.40 s, `walking` 1.20 s, `cough` 1.70 s. Names do not establish whether clips loop, contain root motion, or play correctly. The seated clip may be a transition rather than a usable idle.

The original glTF has no morph targets and no obvious facial-control bones. The generated FBX now adds authored facial blendshapes for expression, eyelids, eye direction, and speech, while preserving all six clips. The seated clip is usable as the prototype's base loop. See [Alex performance](docs/ALEX_PERFORMANCE.md). The source is [Cool Man by ardhanaputra on Sketchfab](https://sketchfab.com/3d-models/cool-man-ad14b71697dd4ea7836c1f06c75e5f72); Sketchfab API metadata confirms CC BY 4.0. Attribution and conversion changes are recorded in `ASSET_CREDITS.md`.

The `unity` project now uses Unity 6000.6.0f1, URP, and OpenXR. Blender 5.2.1 handled the character conversion; Meta Horizon Link is installed. Speech dependencies use a project-local Python 3.11 environment. The current development host reports an RTX 5090 with 32 GB VRAM; the user's stated RTX 4090 remains the performance target to validate.

## System design

```text
Quest microphone
  -> Unity recording / turn detection
  -> local speech-to-text service
  -> dialogue model + character facts + session memory
  -> validated speech segments and performance cues
  -> text-to-speech service
  -> Unity audio playback + subtitles + character performance
```

Unity owns the scene, input, audio playback, and animation. A separate local service owns model loading, transcription, dialogue requests, speech generation, and session state. Keep model work off Unity's main thread. Use a loopback HTTP/WebSocket interface with replaceable provider adapters.

Proposed speech candidates: faster-whisper for STT; Kokoro as a compact voice baseline and Chatterbox as an expressive candidate. The preferred dialogue candidate is now [HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF), selected by the user. Preserve the previous EVA-Qwen2.5-32B-v0.2-GGUF as a behaviour comparison and fallback; its exact quantization and backend remain unknown. Newer architecture does not establish better performance as Alex. Compare character consistency, restrained emotional portrayal, cue validity, and response latency using the same conversations.

Use Qwen3.8's non-thinking mode for live dialogue. The [upstream card](https://huggingface.co/Qwen/Qwen3.8-27B) documents `chat_template_kwargs: {"enable_thinking": false}` for compatible servers. Check that the selected runtime applies it with the model's embedded template. No reasoning, internal monologue, or control text should reach speech or subtitles. Exclude separate reasoning fields or explicitly delimited reasoning blocks before validating speech segments. Never forward partial raw generation directly to TTS. Hiding generated reasoning does not eliminate its latency. Keep EVA's template and settings separate if using it for comparison.

The 4090 has 24 GB VRAM shared by rendering and AI. The [HauhauCS download table](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF) lists IQ4_XS at 15.71 GB and Q4_K_P at 17.92 GB. Start with IQ4_XS for more headroom; compare Q4_K_P if measurements justify it. These are file sizes, not total runtime memory. Allow for context, inference workspaces, speech, and the VR runtime. A smooth combined workload remains unverified.

Start around a 4K context window, one session, text-only input, and MTP disabled to establish a baseline. Profile while rendering the Unity test scene. Compare partial CPU offload, CPU-based speech where practical, and reduced inference batch sizes if needed. Expand context only after checking memory and continuity during longer sessions.

The publisher recommends a current Qwen3.8-capable llama.cpp build. Embedded MTP is optional; its separate FastMTP path requires an additional file and runtime patch. Treat these as later experiments. The advertised speedups were measured on different GPUs and workloads, so measure end-to-end dialogue latency and VR frame timing locally. The release label does not imply that Alex should behave aggressively. Pin the successful runtime revision and model checksum during implementation.

### Dialogue and performance contract

Use structured segments internally. Inline bracket tags remain a possible adapter for models that cannot reliably generate the structure.

```json
{
  "segments": [
    {
      "text": "Oh, well... I've been feeling sad lately.",
      "emotion": "sad",
      "intensity": 0.6,
      "gesture": "look_down",
      "voice_style": "subdued"
    }
  ]
}
```

This is a proposed contract, not a statement that a TTS provider accepts these fields. A voice adapter maps supported styles to provider-specific controls. Unsupported styles use normal speech. Only validated spoken text is sent to synthesis; body cues never become narration.

Initial emotion set: neutral, anxious, sad, frustrated, relieved. Initial actions: none, look down, glance away, nod, hand fidget, wince, wipe tear. Expand after these work. Treat crying as a coordinated performance with voice/breath, face, and body components. Treat depression as a scenario-level description if introduced later, rather than a one-shot animation.

The service assigns a turn ID and segment IDs. Unity starts each segment's cues when its audio begins, blends persistent emotion smoothly, and prevents conflicting gestures. Initially use sentence-sized segments and allow at most one main gesture per segment. Only synthesize a segment once its structure is complete and valid.

On interruption or reset, cancel pending generation, stop playback, clear queued audio/actions, and discard late responses from the old turn. On malformed output, allow a bounded repair attempt; otherwise surface a retry state without reading raw structured output aloud. Unknown cues are ignored or mapped to a neutral fallback. Clamp numeric intensity to the permitted range. Player transcripts are dialogue input, never executable animation commands.

### Character continuity

Separate immutable biography, current session state, and performance output. Track what Alex has disclosed, recent conversation, and proposed simulation variables such as trust, distress, and willingness to speak. These variables are authoring controls, not clinical measurements.

Preserve the facts that his family is safe, his home is lost, and he has a back injury. Convert the original first-person action prose into performance cues and spoken dialogue. Keep replies conversational and usually short enough for natural turn-taking. Emotional changes should be gradual; recounting an emotion does not necessarily mean displaying it now.

## Milestones in execution order

### 1. Establish the project and inspect the character

Create a Unity project under `unity/`, using a stable supported Unity 6 release, URP, OpenXR, and a compatible XR Interaction Toolkit version. Record and pin exact versions after verifying installation. Set up version control, appropriate generated-file exclusions, and a separate service environment. Preserve supplied source files.

Import the character using a compatible glTF importer or a controlled Blender-to-FBX export. Check materials, human scale, orientation, skeleton mapping, root motion, each supplied clip, and seated contact with a chair. Inspect the model at conversational distance. Identify which joints are deform bones and which are controls before retargeting.

**Deliverable:** a desktop scene with the character and a short asset audit, including a decision to retain, modify, or replace it.

**Complete when:** the project opens cleanly, the character renders and animates, the seated pose is understood, and the facial-rig route is selected. If facial rework is extensive, retain this model only as a temporary body prototype and select a replacement before final animation work. Confirm asset rights before packaging it for distribution.

### 2. Prove speech and dialogue before adding scene complexity

Create a small service harness supporting text input and microphone recordings. Set up the selected Qwen3.8 IQ4_XS with a compatible local backend, recording quantization/context/template/sampling settings and verifying non-thinking output. If the existing EVA is available, preserve its configuration and run the same character examples as a comparison. Port Alex's profile and example exchanges into a versioned character configuration. Compare STT accuracy on actual headset recordings. Audition the same lines with neutral, anxious, defensive, and subdued delivery in candidate voices. Include short and long replies, pauses, and unusual names.

Validate the segment contract and maintain session memory. Test whether requiring structured cues changes the selected model's roleplay quality, and use backend-supported constrained output if available. Include tests that reasoning/control text stays out of both speech and subtitles, including when delimiters arrive across streamed chunks. Time transcription, model response, speech generation, and time to first audible reply separately. Profile Qwen3.8 while the milestone-1 scene is rendering to expose contention early. Once the baseline passes, compare embedded MTP with it disabled; evaluate any custom acceleration only if useful and compatible with constrained output. Keep API alternatives configurable; no silent switch to a paid service.

**Deliverable:** a repeatable local conversation test with a selected baseline model/voice and measured timings.

**Complete when:** a ten-turn conversation preserves core facts, all speech comes from the text fields, invalid cues fail safely, and the voice is acceptable. A provisional goal is typical short-turn speech starting within about 2–3 seconds of the player finishing; report measured median and slow cases rather than claiming this in advance.

### 3. Build the first conversation in VR

Create a room blockout with two chairs, a small table, basic lighting, and a seated player origin. Connect Unity to the service. Start with push-to-talk to make turn boundaries predictable. Add subtitles, microphone selection, pause, reset, and explicit interruption. Include desktop input for rapid testing.

Verify Quest microphone routing and spatial voice playback. Confirm comfortable eye height, patient distance, recentering, and readable subtitles with the headset on.

**Deliverable:** a Windows build in which the player can sit opposite Alex and speak through Quest Link.

**Complete when:** ten minutes of conversation works in the headset, reset removes old context and pending actions, and interruption never allows old queued speech to resume. Profile rendering while the models are active.

### 4. Add the coordinated character performance

Implement a persistent seated base pose, breathing, blinking, gaze, emotional facial blends, and limited upper-body gestures. Add speech-driven mouth shapes using the selected facial rig. Prototype audio-driven mouth motion first if necessary, then improve articulation/timing.

Build a manual cue panel before connecting live LLM decisions. Test gestures independently, then run scripted speech segments, then enable model-generated cues. Use controlled recordings or generated nonverbal audio for crying if the selected TTS cannot produce it reliably.

**Deliverable:** the character speaks, looks, and moves consistently from the same segment cues.

**Complete when:** cues follow audio playback, emotion transitions do not snap, the mouth stops on interruption, and gestures do not pull hands through the body or displace the character from the chair. Repeated cues should not restart animations every frame or trigger constant fidgeting.

### 5. Furnish and light the consultation room

Choose the final visual style to fit the selected character. Make the room shell and simple custom props in Blender/Unity. Source free furnishings with a consistent style; document each asset's source, license, and modifications.

Essential set: two chairs, small table, tissue box, water cup/bottle, lamp, rug, window treatment, and restrained wall decoration. Add a plant or shelf only if it improves the scene. Keep the patient's face visible and the environment calm.

Kenney Furniture Kit is a CC0 option for a stylized prototype. Poly Haven offers CC0 models, materials, and lighting assets for a more realistic direction; inspect and optimize individual assets. Do not mix the two styles indiscriminately.

**Deliverable:** a coherent furnished room viewed at headset scale.

**Complete when:** scale, chair contact, lighting, stereo rendering, and material appearance hold up in VR without breaking the rendering budget.

### 6. Validate the whole session and package the prototype

Add voice activity detection and hands-free interruption after push-to-talk works reliably. Handle silence, tentative pauses, background noise, and the character's voice leaking into the microphone. Tune endpointing so hesitation does not repeatedly cut the player off.

Run a repeatable session covering rapport building, short answers, sensitive questions, neutral or dismissive player responses, silence, interruptions, and reconnect/reset. Check character consistency and believable pacing; avoid assuming every supportive phrase must lower distress.

Measure CPU/GPU frame times, VRAM, transcription accuracy, and median/tail response latency during a longer session. At 90 Hz, the nominal frame interval is about 11.1 ms; maintain headroom rather than treating that number as an allocation for every subsystem. Check actual delivered headset frames and dropped/reprojected frames. Reduce model load, inference batch sizes, or scene cost where measurements indicate a problem.

**Deliverable:** a Windows prototype, startup instructions, pinned dependency/model versions, asset credits, and a short list of measured limitations.

**Complete when:** the acceptance checks below pass on the target PC and Quest 3. Headset comfort and final microphone/performance checks require the user wearing the headset; automated desktop tests cannot establish those results.

## Acceptance checks for the first playable version

- A complete seated session works with local providers after required models are downloaded.
- Alex maintains supplied biographical facts and remembers relevant details within the session.
- TTS and subtitles never expose JSON, action tags, reasoning blocks, or first-person stage directions as dialogue.
- Emotion and gesture cues correspond to the currently playing speech and transition smoothly.
- Interruption stops audio/actions and prevents stale results from resurfacing.
- Pause/reset and service errors recover visibly without freezing Unity.
- A ten-minute session runs at the agreed headset resolution/refresh settings without sustained inference-related frame drops.
- Voice and facial performance are reviewed together at actual conversational distance.

Use focused automated checks for parsing, cue validation, cancellation, and state reset. Use recorded speech samples for STT checks, a repeatable conversation set for model behaviour, and headset playtests for comfort and visual performance.

## Proposed working layout

```text
Psychology_VR/
  EXECUTION_PLAN.md
  Character description.txt       original source
  Persona Description.txt         original source
  Authors note.txt                original source
  man/                            original supplied asset
  unity/                          Unity project
  services/                       local STT, dialogue, and TTS adapters
  characters/alex/                profile, prompt, examples, cue configuration
  docs/                           setup, asset audit, benchmark results
```

This layout is now implemented. Downloaded model weights and runtimes are in ignored `.cache` and `.tools` directories. Keep service credentials outside source files and built game assets.

## Deferred scope and open information

After the first playable version: standing and leaving the room, further trauma scenarios, multiple patients, more varied emotional performances, and standalone Quest deployment. Leaving the room requires separate standing, locomotion, navigation, and session-ending behaviour.

The selected Qwen IQ4_XS weights have been downloaded, checksum-verified, and tested with pinned llama.cpp b10909. EVA remains an untested comparison/fallback. Character licensing is verified. A working Quest connection, microphone routing, sustained frame timing, and a longer character-consistency evaluation remain setup and acceptance checks. English and the consultation-room adaptation remain working assumptions.

Do not assign a calendar completion date until the model import and speech tests establish whether facial work or runtime integration dominates the effort. Milestones 1 and 2 determine the credible estimate for the remaining work.

## Verified reference sources

- [Unity XR Interaction Toolkit](https://docs.unity3d.com/Packages/com.unity.xr.interaction.toolkit@3.0/manual/index.html): stationary XR origin, interactions, and desktop simulation support.
- [Unity glTFast](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.0/manual/index.html): glTF import option; select a package version compatible with the chosen Editor.
- [Kenney Furniture Kit](https://kenney.nl/assets/furniture-kit): free CC0 furniture source.
- [Poly Haven license](https://polyhaven.com/license): CC0 asset terms.
- [Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html): body animation source and permitted uses; supplied model provenance is still unconfirmed.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): local CPU/GPU transcription.
- [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M): compact local speech candidate.
- [Chatterbox](https://github.com/resemble-ai/chatterbox): expressive speech candidates; available controls differ by variant.
- [Groq rate limits](https://console.groq.com/docs/rate-limits): optional free-tier service limits, to recheck when configuring a provider.
- [Meta hardware setup](https://developers.meta.com/horizon/design/prototype-setup-hardware/): headset connection setup.
- [EVA upstream model card](https://huggingface.co/EVA-UNIT-01/EVA-Qwen2.5-32B-v0.2): roleplay finetune description and ChatML format.
- [EVA GGUF sizes](https://huggingface.co/tensorblock/EVA-Qwen2.5-32B-v0.2-GGUF): a published quantization size reference, not confirmation of the user's exact file.
- [Selected HauhauCS Qwen3.8 GGUF](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF): file sizes and publisher-described runtime/acceleration requirements.
- [Qwen3.8 upstream card](https://huggingface.co/Qwen/Qwen3.8-27B): thinking control and model details; upstream benchmarks do not validate this modification's roleplay quality.
- [Cool Man source metadata](https://api.sketchfab.com/v3/models/ad14b71697dd4ea7836c1f06c75e5f72): title, creator, and verified CC BY 4.0 license.

References were checked during this planning conversation. Package/model availability and free-tier terms should be checked again when installing or enabling a service.
