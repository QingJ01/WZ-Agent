# DEVICE KNOWLEDGE BASE

## OVERVIEW
MuMu/emulator plumbing: window discovery, ADB transport, scrcpy stream acquisition.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| ADB wrapper | `ADBTool.py` | shell/tap/swipe/base connectivity |
| Emulator discovery | `emulator_manager.py` | MuMu window/port/ADB heuristics |
| Video stream | `ScrcpyTool.py` | scrcpy client, stream patching, warmup, window checks |

## CONVENTIONS
- MuMu is the primary target; fallbacks exist but are secondary.
- `ADBTool` is the base abstraction; `ScrcpyTool` builds on it.
- Window checks and ADB path checks are defensive and noisy by design.

## ANTI-PATTERNS
- Do not assume emulator-independent behavior.
- Do not edit only one side of window/ADB detection; these files form one subsystem.
- Do not remove fallback paths unless the runtime environment is also simplified.

## NOTES
- `ScrcpyTool.py` patches scrcpy internals and filters stderr; debugging stream issues often starts here.
- `data/mumu_config.json` stores discovered window/device state used by this subsystem.
