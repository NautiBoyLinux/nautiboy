# Development

The application uses a `src/` Python layout. Protocol construction, image
processing, udev discovery, hidraw access, application state, and Qt widgets are
separate modules. USB operations execute in a dedicated Qt worker thread.

Run offline tests with `pytest`. Tests must never require a real hidraw device;
all backend file descriptors, writes, ioctls, and discovery refreshes are mocked.

Hardware tests are manual-only. Before any release adds a command or report ID,
document its source, persistence implications, failure behavior, and recovery
path. Persistent-storage and firmware commands are explicitly out of scope.
