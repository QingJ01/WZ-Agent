# CONFIG KNOWLEDGE BASE

## OVERVIEW
Central configuration surface. Treat `config/__init__.py` as the public API; submodules hold actual values.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| Core runtime constants | `base.py` | FPS, ADB path, model paths, thresholds, coordinate transforms |
| Template ROI / match thresholds | `templates.py` | Fixed-layout screen assumptions |
| Emulator discovery rules | `emulator.py` | MuMu paths, ports, window title/class heuristics |
| Key mappings | `keys.py` | Skill/move/input constants |
| Hero/lane/name mappings | `heroes/mapping.py` | Chinese↔pinyin, lane groups, suffix helpers |
| Support-hero tuning | `heroes/support_config.py` | follow distance, priorities, auto-maintenance |
| Hero-state configs | `heroes/state_configs.py` | hero-specific detection regions / color settings |

## CONVENTIONS
- Keep exported names reachable through `config/__init__.py`.
- Use Chinese hero names for authoritative config keys.
- Group config by domain, not by consumer module.
- Paths derive from `PROJECT_ROOT`; do not hardcode model/data paths outside config.

## ANTI-PATTERNS
- Do not scatter magic numbers into runtime modules if they are reused.
- Do not change MuMu resolution-dependent constants without checking templates and coordinate conversions together.
- Do not bypass `mapping.py` for ad-hoc hero-name conversions.

## NOTES
- `base.py` and `templates.py` are strongly coupled to 1920×1080-ish capture assumptions.
- `mumu_config.json` in `data/` reflects discovered runtime state; keep docs/config distinction clear.
