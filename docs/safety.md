# Safety model

- Only allowlisted VID/PID/interface combinations are eligible.
- Identity is re-read from sysfs immediately before every device open.
- The GUI never runs as root and never selects arbitrary hidraw paths.
- Images are decoded and re-encoded with strict dimensions and byte limits.
- Each transfer is finite. A named 1,000 ms timer may schedule the same validated
  in-memory JPEG again only after the previous transfer completes.
- Timer events are discarded while a transfer is in flight. Failures stop the
  timer immediately and are never retried automatically.
- Short writes and disconnects fail immediately.
- The only feature reports defined are firmware read `0x05` and the two known
  OpenLinkHub hardware-mode restoration reports.
- Manual restore, disconnect handling, and normal exit stop refresh first.
- Normal exit restores hardware mode only after this session sent an image.
- No persistent storage, firmware flashing, cooling, pump, fan, RGB, brightness,
  frame-rate, or rotation operation exists in the codebase.
