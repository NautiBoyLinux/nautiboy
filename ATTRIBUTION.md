# Attribution

The Corsair Nautilus LCD report framing used by this project was informed by the
GPLv3 OpenLinkHub project by Nikola Jurkovic and contributors:

- https://github.com/jurkovic-nikola/OpenLinkHub
- Dedicated Nautilus support introduced in commit
  `39097f6815027ef096c7e2169614a2d418bdf08b`
- Nautilus IDs added to shared LCD discovery in commit
  `1233b659838e69c1e37b8bd5758ce0c4bcfe650d`

The implementation here was written as a small, isolated Python backend from the
documented protocol behavior and local hardware-validation notes; it is not a
source translation of OpenLinkHub.

The protocol was validated on a Corsair Nautilus LCD Cap `1b1c:0c57`, firmware
`0.3.0.5`: a 480×480 JPEG was successfully transferred as 47 1024-byte volatile
reports, after which the controller returned to its existing hardware-mode GIF.

Corsair product and brand names belong to Corsair. This is an independent,
unofficial open-source project and is not endorsed by Corsair.
