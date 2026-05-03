# GAME_MANAGER KNOWLEDGE BASE

## OVERVIEW
UI state machine and action layer. This package decides “where in the game UI are we?” and “what click should happen next?”.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| State catalog | `state_definitions.py` | `GameState`, `STATE_SIGNATURES`, descriptions/groups |
| Transition rules | `state_transitions.py` | legal next-state graph |
| Main detector | `state_detector.py` | orchestration hub; wires matcher, transitions, hero/popup/AI handlers |
| Template engine | `template_matcher.py` | MTM/OpenCV template matching |
| Click backend | `click_executor.py` | taps, swipes, coordinate conversion |
| Popup recovery | `popup_handler.py` | unknown-state remediation |
| Hero pick flow | `hero_selector.py` | select/verify/confirm hero |
| AI mode flow | `states/ai_mode_handler.py` | battle AI mode setup clicks |
| Transition logging | `state_visualizer.py` | state history/progress |

## FLOW
`Master_Auto.main()`
→ `TemplateMatcher`
→ `ClickExecutor`
→ `GameStateDetector`
→ detect state using `STATE_SIGNATURES`
→ validate against `STATE_TRANSITION_RULES`
→ delegate side effects to popup/hero/AI handlers
→ execute taps/swipes through `ClickExecutor`

## CONVENTIONS
- `state_detector.py` is the orchestration hub; avoid duplicating state logic elsewhere.
- Add new UI states in `state_definitions.py` and transition edges in `state_transitions.py` together.
- Prefer template names aligned with image asset names.

## ANTI-PATTERNS
- Do not add clicks directly into random detection code if a handler exists.
- Do not add a new state without updating both signature metadata and transitions.
- Do not loosen thresholds casually; false positives cascade through the whole flow.

## NOTES
- This package is the best child doc candidate because it has the clearest internal architecture and highest runtime centrality.
