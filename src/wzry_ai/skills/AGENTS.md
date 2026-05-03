# SKILLS KNOWLEDGE BASE

## OVERVIEW
Hero skill execution layer. Shared base plus hero-specific logic files.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| Shared base loop | `hero_skill_logic_base.py` | queue consumption, maintenance, attack/skill helpers |
| Generic manager | `generic_skill_manager.py` | fallback/generalized skill execution |
| Hero-specific logic | `yao_skill_logic_v2.py`, `caiwenji_skill_logic_v2.py`, `mingshiyin_skill_logic_v2.py` | primary active implementations |
| Config schemas | `hero_skill_configs.py`, `skill_context.py`, `skill_types.py` | shared data definitions |
| Legacy manager | `hero_skill_manager.py` | file says old/kept for compatibility |

## CONVENTIONS
- New hero behavior should extend the v2/base path, not the legacy manager path.
- Skill logic consumes queue-fed state rather than querying the world directly.
- Key constants come from `config.keys` via the base module.

## ANTI-PATTERNS
- Do not build new hero features on top of deprecated `hero_skill_manager.py` unless explicitly reviving legacy path.
- Do not hardcode keys inside hero modules.
- Do not duplicate maintenance logic already present in the base class.

## NOTES
- Current supported support heroes are config-driven; battle registry decides which skill class to load.
