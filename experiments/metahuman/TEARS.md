# Crying tear-film audition

The first placement is calibrated on the existing Dominic-derived Alex face.
The source speaking animation, audio and original skin materials are unchanged.

`/Game/Audition/Tears/M_TearFilm` is a deferred decal with a narrow procedural
wetness mask, low roughness and a curved normal profile. Two asynchronous
droplet highlights travel along the trails. This is a native rendered effect,
not a video overlay. `Wetness` is independently keyable, and `Phase` separates
the two cheeks' timing. No third-party tear texture was downloaded.

`/Game/Audition/Tears/LS_CryingTears` copies the approved crying speech sequence.
Two narrow decal projectors are placed beneath lower-eyelid landmarks and
follow 257 baked head transforms. Parent bone transforms are composed from the
actual facial AnimSequence; simply seeking a LevelSequencePlayer in an editor
script does not reliably update evaluated bone positions each frame.

The preview ramps Wetness from zero to 0.9 over 40 frames, holds through frame
220, and returns to zero by frame 256. The trails alter normals and roughness;
they do not repaint the face white. Projected trails conform to the rendered
skin surface, but their placement follows the head rather than individual
deforming cheek vertices. Extreme expressions and other identities need their
own placement review. Droplets are shader highlights, not free-falling fluid
simulation or additional physics bodies.

Unreal deferred-decal UVs are local Z,Y; the shader remaps them to horizontal
and downward coordinates. Its normal basis also differs from a conventional
mesh UV basis. Material parameter keys are written in sequence ticks; transform
scripting-channel keys are written in display frames. Preserve both conversions
when editing the effect.

Build in a normal Unreal Editor session with
`-ExecutePythonScript=.../tools/metahuman-tears-build.py`, then render with
`tools/metahuman-audition-render.py -mhTears`. Run
`tools/package-metahuman-tears.py` with the livelink Python environment to encode
the before/after video and verify its frames and audio.

Review: `http://127.0.0.1:8798/metahuman-tears/`.
Generated native assets and reports are local. Unity integration, VR cost and
other identities' tear placements are not validated by this preview.
