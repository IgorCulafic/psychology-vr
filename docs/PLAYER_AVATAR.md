# Seated player and live jumper integration

The main `Consultation.unity` scene now instantiates `JumperCandidate.prefab` as Alex and `SeatedPlayer.prefab` as the player. Alex's character profile and conversation protocol are unchanged. The separate jumper audition remains available.

## Player

The player is a derived copy of the supplied dressed jumper rig, with a blue-green sweater tint. Its facial meshes are removed, and 9,516 head/eyelash triangles are removed from a separate body mesh asset. The original character asset is untouched. The seated legs stay in place; shoulders and torso respond to headset lean and yaw, while two-bone arm IK follows the controllers without stretching bone lengths.

- **Left X:** recenter position and facing toward Alex. Recenter runs automatically on the first tracked headset frame. Desktop R and the Recenter button perform the same action when a headset is tracked.
- **Controller grip:** curl the middle, ring and little fingers and oppose the thumb.
- **Controller trigger:** curl the index finger. The right trigger also selects menu buttons while the menu is open. **Right B** opens/closes the menu and pauses/resumes speech.
- **Right A:** hold to record speech and release to send, as before.
- Lost controller tracking returns that hand to its resting seated pose. Unreachable positions clamp to arm length. The camera retains the headset position and is not clamped to the avatar.

Head and controller positions use the same calibrated tracking origin. The headset pose is refreshed again before rendering. Initial virtual eye position is 1.30 m high and 8 cm forward of the seated origin, above the sweater collar. `SeatedPlayerAvatar.wristOffset` is the adjustable controller-to-wrist offset.

This is a seated controller avatar: no optical hand tracking, finger tracking, walking, full-body tracking, prop grabbing, or physical hand/table collision is implemented. Controller grip offsets, reach proportions, comfort, and sustained frame rate still need a Quest 3 test. Existing clothing deformation at extreme arm bends and detailed finger polish remain deferred.

## Live facial performance

`FacialPerformance` retains audio-clock mouth cues, interruption, pause/resume, blinking and gaze. `CCFacialRig` maps the jumper's authored facial controls for all 20 delivery states and coordinates its jaw and eye bones. Speech has priority over emotional lip tension for consonant closures. Tears use the jumper's skin surface and its eye height; flushing affects the head material only. `PerformanceDriver` uses the stable seated pose instead of a legacy animation clip for this model.

`CandidateSeatedPose` works at the live actor's translated and rotated room position. The candidate preview component is not added to the live character.

## Build and verify

Open the main scene and use **Psychology VR → Build Windows prototype**. To regenerate the derived player asset and integrate both prefabs, use **Psychology VR → Integrate jumper and player and build**. The output remains `unity/Builds/Windows/AlexPrototype.exe`.

Desktop integration diagnostic (no services needed):

```powershell
./unity/Builds/Windows/AlexPrototype.exe --desktop --integration-preview --capture-path D:\AI\Psychology_VR\docs\generated\consultation-integration\preview.png -logFile D:\AI\Psychology_VR\docs\generated\consultation-integration-runtime.log
```

It saves room and first-person screenshots, checks head removal, arm reach, finger movement, headset-driven torso movement, tracking loss and unreachable targets, then runs the 20-state facial/audio diagnostic including tears, pause/resume, interruption and gaze. These are simulated tracking checks; they do not certify real headset behavior.
