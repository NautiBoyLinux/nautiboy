# Validated protocol subset

Version 0.1 implements only the subset validated on a Corsair Nautilus LCD Cap
`1b1c:0c57`, interface 0, firmware `0.3.0.5`.

## Volatile JPEG report

Each output report is 1024 bytes:

| Offset | Value |
|---:|---|
| 0 | report ID `0x02` |
| 1 | LCD data operation `0x05` |
| 2 | zero |
| 3 | `0x01` for the final report, otherwise zero |
| 4 | zero-based packet index |
| 5 | zero |
| 6–7 | JPEG bytes in this report, little-endian |
| 8–1023 | up to 1016 JPEG bytes, then zero padding |

The JPEG must be non-empty, complete, and no larger than 260,096 bytes. At most
256 reports can be represented by the one-byte index. The final flag is applied
to the final report whether its payload is full or short.

The application may repeat this same volatile, fully bounded transfer every
1,000 ms while displaying a static image. Retransmission adds no report type and
does not alter packet framing or persistent controller storage.

## Feature reports

- Firmware: read report `0x05` into exactly 33 bytes; a dotted ASCII version is
  decoded starting at byte 6.
- Hardware mode: send `03 1e 01 01`, then `03 1d 00 01`.

No generic feature-report API is exposed. This prevents callers from constructing
unreviewed report IDs through the v0.1 backend.
