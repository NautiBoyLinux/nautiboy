# Background, tray, and single-instance behavior

With the system tray attached, the window close button hides the existing main
window. Static refresh or GIF scheduling continues unchanged, selected media is
retained, and no restore report is sent. The first hide in a process may show a
native informational notification.

The tray provides Open NautiBoy, Restore Hardware Mode, and Quit NautiBoy.
Restore leaves the process running. Quit first prevents new scheduled frames,
then queues the validated restore operation behind any device transfer already
in progress. After restoration, device monitoring and worker threads stop, the
tray icon disappears, and Qt exits. Provider dialogs are rejected so their
network worker can cancel outstanding replies and stop.

NautiBoy acquires a per-user `QLocalServer` before constructing the main window.
A later launch connects with `QLocalSocket`, sends a small activation message,
and exits before device discovery. Stale filesystem sockets are removed only
after a failed connection proves that no listener exists. Linux abstract local
sockets are preferred when Qt provides them.

Optional per-user graphical-session autostart is documented in
[`autostart.md`](autostart.md). It starts through the same single-instance and
tray paths and never selects or sends media automatically.
