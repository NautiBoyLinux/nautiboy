# Display protocol research

This document records implementation inputs, not permission to operate hardware.
All non-Nautilus adapters remain absent and write-disabled.

## Corsair Nautilus LCD Cap

`1b1c:0c57`, interface 0 is the existing native adapter. It uses 1,024-byte
hidraw output reports carrying a baseline 480x480 JPEG, feature reports for
firmware/session state, one in-flight transfer, a 1,000 ms volatile keepalive,
and the validated hardware-mode restore pair. See `protocol.md`; those files are
unchanged. No other Corsair PID inherits this protocol.

OpenLinkHub lists `1b1c:0c55` through the same upstream implementation, making
it a promising research target, but its descriptor, firmware and behavior must
be captured independently before NautiBoy can share an adapter.

## NZXT Kraken Z3, 2023 and 2024

The pinned liquidctl `KrakenZ3` driver provides the most complete next-adapter
reference:

- a 64-byte HID command/status channel plus USB bulk OUT endpoint `0x02`;
- startup commands `70 02 01 b8 <interval>` and `70 01`, followed by firmware
  (`10 01`) and LCD-info (`30 01`) reads;
- brightness/orientation readback from the LCD-info response and `30 02`
  updates; orientation is encoded in 90-degree steps;
- 320x320, 240x240, or 640x640 targets selected by exact PID;
- static RGB pixel preparation, firmware-2 RGB565 preparation, and GIF
  preparation; older generations use a 24,320 KB device asset budget;
- a bucket query/delete/setup/start/bulk/end/switch sequence for the original
  protocol; firmware-2 2023 static transfer uses a different bulk header and a
  documented initial double send;
- bulk chunks of 512 bytes on Z3 and up to 2 MiB on listed 2023/2024 devices.

Important limitations: `300c` remains labelled broken upstream, 2023 firmware
2 rejects GIF mode, and uploads use firmware buckets rather than NautiBoy's
current volatile stream. A native adapter needs PID/firmware-specific state
machines, strict memory bounds, readback, and a defined liquid-mode restoration.

## Lian Li Galahad II LCD

`0416:7395` exposes a 64-byte HID PDU protocol. Type-A PDUs cover firmware,
status, pump/fan and lighting; type-B PDUs carry H.264 display frames. Type-A
fields are big-endian and contain a PDU number plus payload length. The screen
depends on a continuous host H.264 stream; liquidctl intentionally leaves
`set_screen` unimplemented.

Before implementation NautiBoy needs an exact type-B header/fragment capture,
accepted H.264 profile/level/pixel format, resolution, frame cadence, shutdown
state, and loss/reconnect behavior. Those facts are not complete in the pinned
source, so no packet builder should be created yet.

## ASUS Ryujin and Ryuo

The cooler-side Ryujin protocol is 65-byte HID with prefix `ec`; it provides
firmware, temperature, pump and fan operations. Its `set_screen` path is
explicitly unimplemented. Ryujin III White reports show a separate `0b05:1936`
"OLED Controller", but no pinned implementation establishes endpoints, media
format, initialization, brightness, rotation, sequencing, checksums, readback,
or restoration. Ryuo I support is fan-only. These records are identification
research, not adapter candidates yet.

## MSI MPG Coreliquid K360

The pinned driver documents a 320x240 display, HID commands, hardware-monitor,
clock, banner, disable, brightness and four-way orientation. Images are cropped
to 240x320 and encoded as BMP before upload. Custom images are written into
device slots and survive power cycles; upstream marks operations unsafe.

That persistence makes it unsuitable for NautiBoy's first additional adapter.
Any future implementation needs explicit user consent, slot ownership and
readback/rollback rules. It must not reuse the Nautilus volatile semantics.

## TRYX Panorama

The confirmed `391a:1021` PASE path is USB printer class `07/01/02`, with direct
usbfs bulk transfers rather than `/dev/usb/lp*`. The pinned implementation uses
TRYX framing with generated protobuf messages, a DeviceInfo readiness response,
bounded bootstrap, Ping keepalive, serialized transfers, H.264 YUV420p at
2240x1080/30 fps, device catalog verification, configuration readback,
brightness, backlight and orientation. It treats partial/unknown writes as
terminal until physical reconnection.

This is sufficiently documented for future native research but too stateful for
an early adapter. Delete, firmware, reset, loader and other destructive commands
must remain permanently outside an initial display-only backend. `18d1:2d03`
is a generic Android accessory identity and requires product/serial/interface
fingerprinting before it can identify a TRYX device reliably.

## Thermalright display controllers

The pinned dedicated implementation documents:

- `0416:5302`: 320x240 HID display, 512-byte chunks, a fixed binary frame
  header and RGB frame payload;
- `0416:5408`: LY bulk JPEG display. Initialization writes a 2,048-byte
  handshake and validates a 512-byte reply. Baseline JPEG is divided into
  512-byte records (16-byte header plus 496 data), padded to a four-record
  boundary, emitted in 4,096-byte writes with a 2,048-byte tail, then followed
  by a 512-byte acknowledgement. The reported panel is 1920x462.

These are realistic native-adapter candidates after exact-device USB descriptor
captures confirm interface and endpoint selection. Brightness, rotation,
readback and a vendor/hardware-mode restore are not established and must remain
unavailable unless independently proven.

## Required promotion gate

For each device PID, promotion to experimental native control requires:

1. exact USB descriptors, interfaces, endpoints/usages and report sizes;
2. exact product/firmware identification beyond VID:PID where ambiguity exists;
3. immutable encoders and packet builders with golden-vector tests;
4. bounded transfer sizes, timeouts, one-operation guards and no backlog;
5. initialization and readback captured on that device;
6. disconnect, short-write and partial-transfer failure rules;
7. a non-persistent operation path, or separately approved persistence design;
8. safe stop/restoration behavior;
9. a reviewed controlled physical test plan.
