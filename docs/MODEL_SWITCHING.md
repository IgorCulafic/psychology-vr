# Dialogue model selection

As of 28 September 2026, Gemma 4 12B QAT Q4 is the chosen development default after the project owner's conversational tests. Bonsai remains an optional comparison, but lost coherence quickly during those tests. Higgs stays BF16; changing the dialogue model does not change the voice reference, speech precision or STT settings.

The [Unity + Gemma memory check](GEMMA_VRAM.md) measured about 18.1 GiB for the project processes and 20.6 GiB across the whole GPU, including other desktop applications. That was a desktop RTX 5090 test, not active Quest Link on a 4090.

- Unity: open **Settings → Dialogue model** and click an installed model.
- Wait until the reply finishes, or explicitly stop it first. The service refuses to change models during generation or unacknowledged playback, including another client's active session.
- The setting applies to the shared local service, including the text tester. Existing conversation history and relationship state are retained; changes are recorded in open session journals.
- Only one dialogue model is loaded at a time. Speech stays loaded. Allow time for a model change before speaking again.
- A missing model is labelled **not installed**. **PC Settings.cmd → 5** installs Bonsai and its required Prism llama.cpp runtime; **6** installs Gemma. Downloads are pinned and checksum-checked. The menu does not download models while playing.

The allowlist is `services/dialogue-models.json`. The active ID is `dialogue_model` in `services/config.local.json`. Legacy PC Settings options 1–4 explicitly select their original hardware presets instead. Bonsai's PQ2 format uses `.tools/bonsai-llama/llama-server.exe`; do not replace it with the generic runtime.

Native clients read `GET /models`, request `POST /models/select` with `{"model_id":"bonsai"}`, and poll `/models` while `switching` is true. Requests accept fixed IDs only. The switch checks the recorded process identity before stopping it, saves the setting after health checks pass, and attempts to restore the previous model if loading fails. Details are in `services/.runtime/model-switch.log`.

Validated locally: the Unity Windows build compiles; Bonsai → Gemma → Bonsai works through the live API with the existing BF16 speech process retained; 136 service tests pass. A Bonsai spoken-response check produced its first available audio segment in 13.6 s on the development RTX 5090 while builds/startup were also running. This is one smoke check, not a 4090 benchmark or a quality rating.
