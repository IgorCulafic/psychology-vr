# Character and situation library

The picker contains **Alex — After the earthquake**, plus three adult profiles adapted from `Simulacija_ENG.docx`: **Nikola (42)** after losing his father, **Stefan (31)** after witnessing a fire, and **Ivan (39)** with work-related exhaustion. See [adult case notes](ADULT_CASES.md) for source mapping, authored details, behavior and validation. The new profiles currently reuse the existing jumper avatar and configured voice; they do not yet have distinct models or voices. Alex's profile was not changed during this addition.

`catalog.json` is the service's library. Each entry has a unique scenario `id`, a `character_id` used to group situations under one person, `character_name`, `age`, `title`, `summary`, `focus`, `avatar_id`, and a `profile` path relative to this directory. Entries sharing a `character_id` appear as situations for that character. Character lists paginate after four entries; situation arrows cycle through that character's entries.

To add a character or situation:

1. Create a profile JSON, using `alex/profile.json` as the structure. Author its name, facts, setting, initial state, opening line and rules. Replace identity-specific rules as well as biography facts. Each situation can have its own file. Initial emotion names must come from the emotion catalog, and intensity must be between zero and one.
2. Add its metadata to `catalog.json`. Keep IDs stable and unique. Set `avatar_id` to a registered appearance; this selects its default model. Profiles must reside inside `characters/`.
3. For a new visual model, register an appearance on the main scene's `PrototypeSession.appearances` array in Unity: ID, display label, prefab, and optional seated animation clip. The supplied CC rig uses the static seated pose; original Alex uses its Legacy sit clip. Other skeletons need the appropriate pose/facial adapter. Existing custom registrations are preserved by the menu build.
4. Optionally add a portrait texture under `Assets/PsychologyVR/Resources/Menu/<character_id>.png`. An image named after an appearance ID overrides the character portrait when that appearance is selected. The two existing Alex portraits are copied from their Unity preview captures by the build helper.
5. Restart the local service to reload profiles, then rebuild Unity through **Psychology VR → Build menu and character library**. Standard Windows builds also synchronize the bundled display catalog. The running game fetches the authoritative metadata from `/catalog` when connecting.

Selecting cards or cycling appearances only changes the pending choice. **Start new conversation** sends the scenario ID to the bridge, retires the previous session ID, invalidates its generation, creates fresh history, applies that profile's starting state, instantiates the chosen model and plays its opening. The bridge uses the selected profile for every later LLM request and reset. Late work or delayed control requests carrying the previous session ID cannot affect the new conversation. Replacement frees the old session slot, so repeated selection does not consume the service's session limit.

Profiles share the currently configured STT/TTS providers and voice. Per-character expressive voices remain future work. The display summary and focus are for the player; the detailed profile is the model's role/context. Physical room selection is not implemented by this catalog.

The new profiles opt into `interaction_style: "patient_v1"`: short answers, gradual relevant disclosure, independent opinions, limited clinical insight, and no therapist/teacher role. `author_notes` contain instructor framing/provenance and are removed before building the model prompt. `disclosure` distinguishes early, follow-up and sensitive information; it guides the model rather than mechanically unlocking facts after a fixed turn count. The original Alex does not opt into this new policy.

The service tests use an additional test-only profile to verify opening, reset, prompt isolation and switching during generation. That fixture is not shipped as a selectable patient.
