# MetaHuman facial audition

The follow-up face-and-neck bake is documented in [REACTIONS.md](REACTIONS.md).
Its review is <http://127.0.0.1:8798/metahuman-neck/>. Core mesh and animation
FBXs are in `exports/reactions`; they are not yet a complete Unity character.

This isolated Unreal 5.8 project tests the existing Android recordings with
MetaHuman Animator's local mono-video solver. The main Unity game is unchanged.

## Current result

- Fear: MySlate_4, 406 frames.
- Crying: MySlate_7, 588 frames.
- Anger: MySlate_8, 670 frames.
- All 1,664 frames returned 251 facial control curves, with no non-finite values
  or missing frame dictionaries. Each take has more than 130 varying curves.
- All three complete performances are now rendered on a Dominic-derived adult
  male MetaHuman, with its full joints-and-blendshapes facial rig and optimized
  high-quality assembly. The review compares the original recording, previous
  Jumper transfer, and MetaHuman Animator transfer at matching timing.
- Review: <http://127.0.0.1:8798/metahuman/>. Static files are in
  `docs/generated/face-library-review/metahuman` relative to the repository root.
- The complete rendered videos decoded successfully: 406 / 588 / 670 frames.
  Facial fidelity still needs the user's review. Body and arm acting, tears and
  redness are not reconstructed or added in this facial test.

Reports: `prepare-report.json`, `solve-report.json`, `curve-validation.json`.
Assembly, sequence export and rendering reports are in `character-report.json`,
`export-report.json`, and `render-report.json`. Packaged frame counts are in the
review folder's `verification.json`.
Generated image sequences and raw curves are local under `media/`; generated
Unreal assets are under `Content/Audition/`. Both are excluded from Git.

## Character assembly status

MetaHuman Creator Core Data is installed. The Dominic preset has been duplicated
to `/Game/Characters/AuditionMale` in this isolated project.

`tools/metahuman-audition-character.py` requests the full joints-and-blendshapes
rig, texture sources, and optimized high-quality assembly. Epic sign-in is
required: the first request opens the system browser for user authentication.
Check `character-report.json` for progress; only `assembled` confirms completion.
`tools/metahuman-audition-export.py` subsequently exports all three performances
onto the assembled character. The video solves already
completed locally; they do not require uploading the recordings.

Choose the character quality after reviewing these expressions. Unity runtime
integration and the remaining three male characters are subsequent work.

The first assembly logged built-in Control Rig reroute-link migration errors.
The retry saved the generated assets; reopening and compiling the saved character
Blueprint passed. Full renders subsequently completed successfully. The original
diagnostics remain in `character-signin-retry.log` and `character-assembly.log`.

## Reproduction

From the repository root:

1. Run `.tools/livelink-venv/Scripts/python.exe tools/prepare-metahuman-footage.py`.
2. Launch `MetaHumanAudition.uproject` in UE 5.8 with
   `-ExecutePythonScript=<absolute path to tools/metahuman-audition-prepare.py>`.
3. After that editor exits, launch it with
   `-ExecutePythonScript=<absolute path to tools/metahuman-audition-solve.py>`.
4. Run `tools/metahuman-audition-character.py` through the same editor argument.
   Complete Epic authentication if prompted. This creates/assembles the male.
5. Run `tools/metahuman-audition-export.py` the same way, then
   `tools/metahuman-audition-render.py`. The renderer keeps the editor alive until
   its queue finishes. A `preview-only.flag` file here limits it to three fear
   frames; omit that file for all three complete takes.
6. Run `.tools/livelink-venv/Scripts/python.exe tools/package-metahuman-audition.py`.

The final renderer uses a fixed square studio camera, manual exposure, and
frame-open sampling to prevent the unanimated default pose appearing at frame 0.

Use a normal editor process, not a rendering-disabled commandlet. Run only one
editor for this project at a time. Unreal needs write access to its normal
per-user cache. The scripts derive repository paths from their own location.
Source recordings are preserved; derived frames retain the original resolution
and are sampled at 30 fps.
