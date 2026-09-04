# Architecture

## Layers

1. `device` reads udev/sysfs identity and reports hotplug changes. It never opens
   a device node.
2. `protocol` constructs and validates byte sequences without filesystem or Qt
   dependencies.
3. `imaging` decodes JPEG/PNG input and returns a bounded 480×480 baseline JPEG.
4. `backends` owns direct hidraw access and revalidates device identity before
   every open.
5. `application` and `models` define state-dependent control policy.
6. `gui` presents state and uses a 1,000 ms timer with an in-flight guard. The
   timer only queues work; every USB operation runs in `DeviceWorker` on its
   dedicated `QThread`.

The direct backend is intentionally small. A future OpenLinkHub adapter can
implement the same `NautilusBackend` protocol, but version 0.1 does not start,
configure, or depend on an OpenLinkHub service.

## State model

- `disconnected`: no supported device
- `ready`: supported device configured and idle
- `sending`: one finite report sequence in progress
- `displaying`: this session successfully sent volatile content
- `restoring`: hardware-mode reports in progress
- `error`: the last operation failed

Send and restore are explicit. After the initial send succeeds, `displaying`
maintains the same in-memory JPEG using bounded one-second refreshes. At most one
refresh may be queued or executing. Any transfer failure stops scheduling and
enters `error` without retry. Manual restore, disconnect, and normal close stop
the refresh timer first. A restore failure leaves the window open for a clear,
manual retry rather than hiding the error.
