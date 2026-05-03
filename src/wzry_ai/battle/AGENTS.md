# BATTLE KNOWLEDGE BASE

## OVERVIEW
Combat decision layer for in-match behavior: FSM, threat analysis, target selection, hero-specific decision makers.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| Combat FSM | `battle_fsm.py` | follow / fight / retreat / recall states |
| World snapshot | `world_state.py` | normalized battle inputs |
| Threat scoring | `threat_analyzer.py` | enemy pressure evaluation |
| Target choice | `target_selector.py` | select practical focus target |
| Hero dispatch | `hero_registry.py` | map hero name → decision + skill logic |
| Support decisions | `generic_support_decision.py`, `yao_decision.py` | hero-specific behavior policies |

## CONVENTIONS
- `hero_registry.py` is the dispatch boundary between battle and skills.
- Keep battle-layer decisions independent from raw UI/template concerns.
- Use `world_state` and threat abstractions instead of passing loose tuples/dicts everywhere.

## ANTI-PATTERNS
- Do not add hero-specific branches directly into generic FSM code if registry dispatch can isolate them.
- Do not couple battle decisions to template/image assets.
- Do not let movement and battle policies drift separately on shared concepts like retreat thresholds.

## NOTES
- This package is smaller than `game_manager` but still a distinct domain with high behavior impact.
