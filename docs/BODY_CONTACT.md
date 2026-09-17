# Body contact for Alex

`BodyContactConstraints` is created automatically by `PerformanceDriver` when the seated rig initializes. It runs at execution order 200, after facial/gaze animation. No scene rebuild or manual component assignment is needed. The player avatar's controller path is unchanged.

## Contact geometry and correction

Four invisible capsules follow the thigh bones, waist/chest and head. The head endpoints follow its final animated orientation. The palm uses four wrist-to-knuckle capsules; every finger and thumb has three segment capsules, including an estimated fingertip beyond the final bone. Queries calculate closest points between finite segments, with a 5 mm body margin and 3 mm margin between hands. They do not require physics rigidbodies or collider synchronization.

After normal arm and finger animation, an iterative pass projects the hand target outside the boundaries and resolves the existing arm solver. Wrist flexion, deviation, forearm roll and elbow limits remain in force. Arm solving during contact does not advance animation time or finger pulses. A correction persists across frames and decays over 0.22 seconds when clear, avoiding an immediate return into the obstacle. Required outward movement is applied immediately to avoid smoothing through the body.

Forearm skinning helpers must be reconstructed from their cached calibration on every arm solve. Reusing a partial twist from the previous contact iteration deformed the sleeve even when the wrist was stationary. This is covered by `ForearmRegression`, which checks both helper rotations and actual baked skin vertices on repeated frozen solves.

If reach limits prevent wrist translation from clearing a blocked digit, a local search reduces only flexion that improves the overlap. It never reverses a hinge or alters spread. Normal articulation gradually restores curl when free. This is a fallback: ordinary tested poses clear through arm correction and retain the expressive finger motion.

The two hands also check each other. Crossing hands separate toward their own sides, then recheck the body boundaries. Wrist correction is capped at 14 cm to avoid a runaway solver. Remaining overlap is measured and reported rather than silently treated as success.

The authored thigh-rest and face-covering poses still supply the desired contact locations. This layer corrects those poses against the moving boundaries. To inspect the boundaries in the Editor, select the runtime actor and enable `Draw Boundaries` on `BodyContactConstraints`.

## Verification

Run `PsychologyVR.Editor.BodyContactChecks.CheckAndBuild` in Unity batch mode to check geometry and build Windows. The checks cover point/capsule overlap, parallel/crossing segments, moving head geometry, deliberately obstructed hands, gradual release, blocked-finger uncurling, and crossing-hand separation.

```powershell
./unity/Builds/Windows/AlexPrototype.exe --desktop --record-alex --finger-motion --body-contact --record-dir "$PWD/.cache/body-contact-final" -logFile "$PWD/docs/generated/body-contact-runtime.log"
```

The contact recording checks every frame, including transitions, across rest, anxiety, frustration, anger, crying, fear, panic, disgust, despondency and tear wiping. It checks body and hand-pair residual overlap, correction engagement, wrist/elbow limits, hand speed, resting stability, and continued finger motion while emotional states are held. Side-view stills are captured separately to inspect hand/body depth.

## Scope

These boundaries approximate the supplied adult character at its current scale. They are not a per-triangle collision system for the deforming skin, clothes or hair. Boundary dimensions need tuning for substantially different body proportions or scale. The pass constrains hands against thighs/torso/head and against the other hand; it does not solve sleeve, elbow, furniture or same-hand finger self-collision. Physical Quest performance and comfort need headset testing.
