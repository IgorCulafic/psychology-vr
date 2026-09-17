# Consultation menu

The game opens with a world-space menu. **Escape** on desktop or **right B** on Quest toggles it. Mouse clicks operate it on desktop; the right-controller ray and trigger operate the same buttons in VR. The ray is visible only while the menu is open.

- **Session:** current scenario, latest character line, desktop text input/Send, Begin or Restart conversation, Stop reply, Return to room.
- **Characters & situations:** grouped character cards, situation details and navigation, visual appearance selection, Start new conversation. Only Alex's earthquake situation has been authored so far. Both existing Alex appearances are selectable.

**Hide descriptions** on the character page enables student view. It hides backstory summaries and teaching focus, and replaces descriptive situation titles with neutral case numbers in both the picker and Session page. Names, ages, portraits and navigation remain available. **Show descriptions** restores the information. The preference persists between launches; it does not change the AI's profile or hide dialogue the character actually speaks.
- **Settings:** speech volume, subtitles, microphone selection, seated recentering, reconnect, character performance preview and Quit game. Volume, subtitle visibility and microphone selection persist between launches.

Opening the menu pauses speech playback and blocks new speech input; a pending model request may finish preparing a reply and waits until the menu closes to play it. Opening while recording discards that partial recording. Closing resumes paused speech. Starting a new conversation cancels pending work and clears the old history instead of resuming it. Recenter also repositions an open menu in front of the player. A trigger already held while opening must be released and pressed again to select a button.

In the room, hold **Space / right A** to record and release to send. Desktop right-mouse look is disabled while the menu is open so it does not compete with menu input. **Left X** still recenters. VR text input does not open a virtual keyboard; use voice outside the menu.

The desk console and permanent desktop options panel have been removed. Subtitles remain in the room when enabled. Developer-facing provider names and emotion previews are inside Settings → Character preview.

Extending the character library is documented in `../characters/README.md`.

## Verification

The menu diagnostic runs against the local bridge and captures every page. It checks desktop UI raycasting/click handling, the controller-ray collider path, appearance switching, fresh scenario starts, speech pause/resume, hidden menu after starting, and saved settings. It restores volume/subtitle preferences after its checks.

```powershell
./tools/launch.ps1 -NoGame
./unity/Builds/Windows/AlexPrototype.exe --desktop --menu-preview --capture-path D:\AI\Psychology_VR\docs\generated\menu\preview.png -logFile D:\AI\Psychology_VR\docs\generated\menu-runtime.log
./tools/stop-services.ps1
```

Output is in `docs/generated/menu/`. The controller path is simulated in this diagnostic; actual Quest 3 interaction comfort still requires a headset test.
