# UTILS KNOWLEDGE BASE

## OVERVIEW
Cross-cutting infrastructure: logging, frame sharing, OCR, input automation, thread supervision, small helpers.

## WHERE TO LOOK
| Need | Location | Notes |
|---|---|---|
| Logging API | `logging_utils.py` | `get_logger`, global logging, throttling/filtering |
| Shared frames | `frame_manager.py` | `SharedFrameManager`, frame cache, scrcpy integration |
| OCR helpers | `ocr_helper.py` | PaddleOCR/EasyOCR wrapper logic |
| Keyboard automation | `keyboard_controller.py` | Win32 key events to emulator window |
| Thread watchdog | `thread_supervisor.py` | auto-restart worker threads |
| Misc helpers | `utils.py` | queue safety, image text overlay, distance helpers |

## CONVENTIONS
- Shared infrastructure belongs here before anywhere else.
- `get_logger(__name__)` is the default logging pattern.
- Keep heavy external integration helpers (`adbutils`, OCR backends, win32) wrapped behind simple functions/classes.

## ANTI-PATTERNS
- Do not create duplicate logging/frame helper code in feature modules.
- Do not make helper APIs silently stateful unless file already documents that pattern.
- Do not mix generic helpers and domain-specific battle/game logic here.

## NOTES
- `frame_manager.py` is more than a helper; it is runtime infrastructure.
- `keyboard_controller.py` is Windows-specific and depends on emulator/window discovery.
