# LCD/AIO hardware knowledge base

NautiBoy separates **recognition** from **control authorization**. The catalog in
`nautiboy.hardware` can name a device and describe public protocol research, but
it never opens hardware. A VID:PID match alone is not permission to write.

Only the locally validated Corsair Nautilus LCD Cap `1b1c:0c57`, interface 0,
is currently supported for control. Its existing backend, packetizer, refresh,
device matching, and restore behavior are unchanged. Every other catalog entry
is recognition-only or records a known-but-unimplemented protocol.

Unknown descriptor, interface, endpoint, report-size, and protocol fields stay
unknown. They must be filled from a descriptor capture or exact-device evidence,
not copied from a neighboring product.

## Native adapter direction

Image, GIF, Thermals, and Creative render device-neutral RGB frames. A native
adapter will own the target resolution, pixel/media encoding, initialization,
handshakes, endpoints/report IDs, checksums, sequencing, bounded scheduling,
readback, disconnect handling, and safe shutdown/restoration. NautiBoy will not
invoke or depend on liquidctl, OpenRGB, OpenLinkHub, SignalRGB, vendor software,
or another control application at runtime.

Before an adapter can move from `protocol_known_unimplemented` to experimental,
it needs exact-device descriptor evidence, offline packet tests, operation bounds,
failure behavior, and a reviewed hardware-validation plan. Experimental support
still requires an explicit user action and must never be authorized by VID:PID
alone.

## Protocol readiness

Strongest next candidates:

1. **NZXT Kraken Z3/2023/2024 family** — liquidctl implements initialization,
   bulk image upload, RGB565 conversion, bucket/frame sequencing, brightness,
   orientation, static images, and supported GIF paths. Product generations
   differ, so each PID still needs exact-device validation.
2. **Thermalright `0416:5408` Trofeo Vision** — a dedicated Linux project
   documents bulk endpoints and baseline-JPEG streaming. It is conceptually close
   to NautiBoy's render pipeline, but its wide panel and handshake are distinct.
3. **Lian Li Galahad II LCD `0416:7395`** — liquidctl documents its PDU framing
   and H.264 screen stream. A safe implementation needs a bounded encoder and
   continuous-stream lifecycle; liquidctl intentionally leaves display control
   unimplemented.
4. **TRYX PASE `391a:1021`** — the printer-class bulk protocol, media conversion,
   configuration readback, and lifecycle are documented, but it is stateful and
   materially more complex. Firmware/delete operations must remain excluded.
5. **MSI Coreliquid K360 `0db0:b130`** — image, brightness, rotation, clock and
   hardware-monitor commands are documented. Image uploads use persistent device
   slots, which conflicts with NautiBoy's current volatile-only safety boundary;
   it is not an early implementation candidate.

ASUS Ryujin/Ryuo display control remains identification-only: upstream supports
cooler telemetry/fans but explicitly does not implement the screen. The Ryujin
III display may enumerate separately as `0b05:1936`.

Corsair `0c33`, `0c39`, and `0c4e`, and TRYX legacy `18d1:2d03`, remain
provisional until exact product/interface/descriptor evidence distinguishes them
from other devices sharing those USB identities.

## Evidence snapshots

Every catalog record carries immutable project, revision, source URL, and scope.
The snapshots used for this catalog are:

- liquidctl `292dc561361cfbc0cdee155c26662131fe160989`
- OpenKraken `c637ca8823d540892b7aa35cba2b4e1c4ccedab9`
- OpenLinkHub `084f5e2c71653b5482b696152ab4abda2f321334`
- Tryx-Linux-GUI `377da9ad934575ab6f4ff0fa59f5001b587fb850`
- thermalright-lcd-control `35b0b29001a31ca80b4a9daa7723029620a8ff6e`
- NautiBoy physical validation tag `v0.4.0-beta.1`

These projects are evidence only and create no NautiBoy runtime dependency.
