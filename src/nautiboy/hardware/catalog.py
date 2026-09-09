"""Evidence-backed LCD/AIO identity catalog.

The external projects cited here are research evidence only.  NautiBoy neither
imports nor executes them at runtime.
"""

from __future__ import annotations

from .models import Confidence, ControlSupport, Evidence, HardwareIdentity

LIQUIDCTL_REV = "292dc561361cfbc0cdee155c26662131fe160989"
OPENKRAKEN_REV = "c637ca8823d540892b7aa35cba2b4e1c4ccedab9"
OPENLINKHUB_REV = "084f5e2c71653b5482b696152ab4abda2f321334"
TRYX_REV = "377da9ad934575ab6f4ff0fa59f5001b587fb850"
THERMALRIGHT_REV = "35b0b29001a31ca80b4a9daa7723029620a8ff6e"


def _ev(project: str, revision: str, path: str, detail: str) -> Evidence:
    roots = {
        "liquidctl": "https://github.com/liquidctl/liquidctl/blob",
        "OpenKraken": "https://github.com/davidboulay/OpenKraken/blob",
        "OpenLinkHub": "https://github.com/jurkovic-nikola/OpenLinkHub/blob",
        "Tryx-Linux-GUI": "https://github.com/DXVSI/Tryx-Linux-GUI/blob",
        "thermalright-lcd-control": "https://github.com/rejeb/thermalright-lcd-control/blob",
        "NautiBoy": "https://github.com/NautiBoyLinux/nautiboy/blob",
    }
    return Evidence(project, revision, f"{roots[project]}/{revision}/{path}", detail)


_LIQUID_RULES = _ev("liquidctl", LIQUIDCTL_REV, "extra/linux/71-liquidctl.rules", "USB identity")
_KRAKEN = _ev("liquidctl", LIQUIDCTL_REV, "liquidctl/driver/kraken3.py", "Kraken identity and display protocol")
_KRAKEN_DOC = _ev("liquidctl", LIQUIDCTL_REV, "docs/kraken-x3-z3-guide.md", "LCD capabilities and dimensions")
_OPENKRAKEN = _ev("OpenKraken", OPENKRAKEN_REV, "README.md", "Cross-checked model dimensions")
_ASUS = _ev("liquidctl", LIQUIDCTL_REV, "liquidctl/driver/asus_ryujin.py", "Cooler identities; screen unimplemented")
_ASUS_DOC = _ev("liquidctl", LIQUIDCTL_REV, "docs/asus-ryujin3-guide.md", "Screen explicitly unsupported")
_ASUS_OLED = Evidence(
    "liquidctl issue 869",
    "issue-869-2026-03-06",
    "https://github.com/liquidctl/liquidctl/issues/869",
    "Observed Ryujin III White companion OLED controller identity",
)
_LIAN = _ev("liquidctl", LIQUIDCTL_REV, "liquidctl/driver/ga2_lcd.py", "GA II identity and non-display controls")
_LIAN_PROTOCOL = _ev("liquidctl", LIQUIDCTL_REV, "docs/developer/protocol/lian_li_ga-2-lcd.md", "H.264 host-streamed display protocol")
_MSI = _ev("liquidctl", LIQUIDCTL_REV, "liquidctl/driver/msi.py", "K360 identity and OLED protocol")
_MSI_DOC = _ev("liquidctl", LIQUIDCTL_REV, "docs/msi-mpg-coreliquid-guide.md", "320x240 screen behavior")
_CORSAIR = _ev("OpenLinkHub", OPENLINKHUB_REV, "99-openlinkhub.rules", "Corsair USB identity")
_NAUTILUS = _ev("OpenLinkHub", OPENLINKHUB_REV, "src/devices/nautilusLcd/nautilusLcd.go", "Nautilus display implementation")
_TRYX = _ev("Tryx-Linux-GUI", TRYX_REV, "README.md", "Printer-class identities and display protocol")
_THERMALRIGHT = _ev("thermalright-lcd-control", THERMALRIGHT_REV, "README.md", "Display identity and transport")


def _kraken(pid: int, model: str, size: int) -> HardwareIdentity:
    return HardwareIdentity(
        "NZXT", "Kraken LCD", model, 0x1E71, pid,
        panel_width=size, panel_height=size, media_transport="USB bulk image upload",
        protocol_family="nzxt-kraken-z3", capabilities=frozenset({"static_image", "animation", "brightness", "orientation", "device_state"}),
        control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED,
        confidence=Confidence.CONFIRMED_UPSTREAM, evidence=(_KRAKEN, _KRAKEN_DOC, _OPENKRAKEN),
    )


def _asus(pid: int, model: str, *, companion: bool = False) -> HardwareIdentity:
    evidence = (_ASUS, _ASUS_DOC, _LIQUID_RULES) if not companion else (_ASUS_OLED,)
    return HardwareIdentity(
        "ASUS", "ROG liquid cooler display", model, 0x0B05, pid,
        media_transport=None, protocol_family=None,
        companion_devices=("0b05:1936 OLED Controller",) if not companion else ("ROG Ryujin III cooler controller",),
        capabilities=frozenset({"integrated_display"}), control_support=ControlSupport.IDENTIFICATION_ONLY,
        confidence=Confidence.CONFIRMED_UPSTREAM if not companion else Confidence.PROVISIONAL,
        evidence=evidence, notes="Cooler telemetry/control is known; the separate display protocol is not implemented upstream.",
    )


HARDWARE_CATALOG: tuple[HardwareIdentity, ...] = (
    HardwareIdentity(
        "Corsair", "Nautilus LCD Cap", "Nautilus LCD Cap", 0x1B1C, 0x0C57,
        ("CORSAIR Nautilus LCD Cap", "NAUTILUS LCD CAP"), 0, 0x03,
        panel_width=480, panel_height=480, media_transport="hidraw JPEG report stream",
        protocol_family="corsair-nautilus-lcd-v1", output_report_sizes=(1024,), feature_report_sizes=(1024,),
        capabilities=frozenset({"static_image", "animation", "volatile_mode", "hardware_mode_restore", "firmware_read"}),
        control_support=ControlSupport.SUPPORTED, confidence=Confidence.LOCALLY_VALIDATED,
        evidence=(_NAUTILUS, _ev("NautiBoy", "v0.4.0-beta.1", "docs/HARDWARE-VALIDATION.md", "Physical validation")),
        notes="The only write-authorized catalog identity; backend also revalidates interface 0 before every open.",
    ),
    HardwareIdentity("Corsair", "Nautilus LCD Cap", "Nautilus LCD Cap variant", 0x1B1C, 0x0C55,
                     ("NAUTILUS LCD CAP",), control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED,
                     confidence=Confidence.CONFIRMED_UPSTREAM, evidence=(_NAUTILUS, _CORSAIR),
                     notes="Upstream shares an implementation; NautiBoy has not validated its descriptor or protocol."),
    HardwareIdentity("Corsair", "Elite Capellix LCD Cap", "Elite Capellix LCD Cap family (0c33)", 0x1B1C, 0x0C33,
                     control_support=ControlSupport.IDENTIFICATION_ONLY, confidence=Confidence.PROVISIONAL, evidence=(_CORSAIR,),
                     notes="USB identity is upstream-listed; exact standalone display fingerprint remains required."),
    HardwareIdentity("Corsair", "Elite Capellix LCD Cap", "Elite Capellix LCD Cap family (0c39)", 0x1B1C, 0x0C39,
                     control_support=ControlSupport.IDENTIFICATION_ONLY, confidence=Confidence.PROVISIONAL, evidence=(_CORSAIR,),
                     notes="USB identity is upstream-listed; exact standalone display fingerprint remains required."),
    HardwareIdentity("Corsair", "iCUE LINK LCD", "iCUE LINK AIO LCD Screen Module", 0x1B1C, 0x0C4E,
                     control_support=ControlSupport.IDENTIFICATION_ONLY, confidence=Confidence.PROVISIONAL, evidence=(_CORSAIR,),
                     notes="PID presence is confirmed, but association with this exact module is not independently established."),
    _kraken(0x3008, "Kraken Z53/Z63/Z73", 320),
    _kraken(0x300E, "Kraken 2023", 240),
    _kraken(0x300C, "Kraken Elite 2023", 640),
    _kraken(0x3012, "Kraken Elite RGB 2024", 640),
    _kraken(0x3014, "Kraken Plus 2024", 240),
    HardwareIdentity("Lian Li", "Galahad II LCD", "Galahad II LCD", 0x0416, 0x7395,
                     product_strings=("LianLi-GA_II-LCD",), media_transport="continuous H.264 over USB HID PDU",
                     protocol_family="lian-li-ga2-lcd", capabilities=frozenset({"video_stream", "device_state"}),
                     control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED, confidence=Confidence.CONFIRMED_UPSTREAM,
                     evidence=(_LIAN, _LIAN_PROTOCOL, _LIQUID_RULES),
                     notes="Display needs continuous host video; liquidctl documents but deliberately does not implement screen control."),
    _asus(0x1988, "ROG Ryujin II 360"),
    _asus(0x1AA2, "ROG Ryujin III 360"),
    _asus(0x1ADA, "ROG Ryujin III White"),
    _asus(0x1ADE, "ROG Ryujin III EVA"),
    _asus(0x1BCB, "ROG Ryujin III Extreme"),
    _asus(0x1936, "Ryujin III OLED/display controller", companion=True),
    HardwareIdentity("ASUS", "ROG Ryuo", "Ryuo I 240", 0x0B05, 0x1887,
                     capabilities=frozenset({"integrated_display"}), control_support=ControlSupport.IDENTIFICATION_ONLY,
                     confidence=Confidence.CONFIRMED_UPSTREAM,
                     evidence=(_ev("liquidctl", LIQUIDCTL_REV, "liquidctl/driver/asus_ryuo.py", "Exact identity; fan-only driver"), _LIQUID_RULES),
                     notes="Linux driver explicitly supports fan control only; display protocol is unknown."),
    HardwareIdentity("MSI", "MPG Coreliquid", "MPG Coreliquid K360/K360 V2 family", 0x0DB0, 0xB130,
                     panel_width=320, panel_height=240, media_transport="HID image upload to device slots",
                     protocol_family="msi-coreliquid-k360", capabilities=frozenset({"static_image", "hardware_monitor", "clock", "brightness", "orientation", "persistent_media_slots"}),
                     control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED, confidence=Confidence.CONFIRMED_UPSTREAM,
                     evidence=(_MSI, _MSI_DOC, _LIQUID_RULES),
                     notes="Upstream image upload is persistent; a NautiBoy adapter requires an explicit persistence safety design."),
    HardwareIdentity("TRYX", "Panorama", "Panorama SE/PASE", 0x391A, 0x1021,
                     product_strings=("RK PASE",), interface_number=0, interface_class=0x07,
                     panel_width=2240, panel_height=1080, media_transport="bidirectional USB printer-class bulk",
                     protocol_family="tryx-kanali-pase", capabilities=frozenset({"static_image", "animation", "video", "brightness", "orientation", "device_state"}),
                     control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED, confidence=Confidence.CONFIRMED_UPSTREAM,
                     evidence=(_TRYX,), notes="Complex stateful protocol; firmware and destructive operations must remain out of scope."),
    HardwareIdentity("TRYX", "Panorama", "Panorama legacy Android-accessory interface", 0x18D1, 0x2D03,
                     media_transport="Android accessory/serial", protocol_family="tryx-legacy-aoa",
                     capabilities=frozenset({"integrated_display"}), control_support=ControlSupport.IDENTIFICATION_ONLY,
                     confidence=Confidence.PROVISIONAL, evidence=(_TRYX,),
                     notes="Generic Google accessory VID and product; exact device fingerprint is mandatory."),
    HardwareIdentity("Thermalright", "Frozen Magic LCD", "Frozen Magic 240/360 HID display", 0x0416, 0x5302,
                     panel_width=320, panel_height=240, media_transport="HID frame transfer", protocol_family="thermalright-hid-type2",
                     capabilities=frozenset({"frame_stream"}), control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED,
                     confidence=Confidence.CONFIRMED_UPSTREAM, evidence=(_THERMALRIGHT,),
                     notes="Some products/resolutions share controller families; fingerprint and handshake must select the exact layout."),
    HardwareIdentity("Thermalright", "Trofeo Vision", "Trofeo Vision LCD", 0x0416, 0x5408,
                     panel_width=1920, panel_height=462, media_transport="USB bulk baseline JPEG stream",
                     protocol_family="thermalright-ly-bulk", capabilities=frozenset({"static_image", "animation", "frame_stream"}),
                     control_support=ControlSupport.PROTOCOL_KNOWN_UNIMPLEMENTED, confidence=Confidence.CONFIRMED_UPSTREAM,
                     evidence=(_THERMALRIGHT,)),
)


def identities_for_usb(vid: int, pid: int) -> tuple[HardwareIdentity, ...]:
    """Return recognition candidates; this function never authorizes I/O."""
    return tuple(record for record in HARDWARE_CATALOG if record.key == (vid, pid))


def identify_usb(vid: int, pid: int, interface_number: int | None = None) -> HardwareIdentity | None:
    candidates = identities_for_usb(vid, pid)
    exact = tuple(record for record in candidates if record.identifies(vid=vid, pid=pid, interface_number=interface_number))
    return exact[0] if len(exact) == 1 else None
