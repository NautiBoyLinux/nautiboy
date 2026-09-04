# Device permissions

NautiBoy uses this narrowly scoped rule:

```udev
# Corsair Nautilus LCD Cap — active local desktop user only
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1b1c", ATTRS{idProduct}=="0c57", TAG+="uaccess"
```

Install it with:

```bash
sudo install -m 0644 packaging/70-nautilus-lcd.rules /etc/udev/rules.d/70-nautilus-lcd.rules
sudo udevadm control --reload-rules
```

Reconnect the LCD's USB connection or reboot. This ensures the new rule is
applied through normal device enumeration. A normal desktop session should then
show an `rw-` ACL for the active user:

```bash
getfacl /dev/hidrawN
```

The `hidrawN` number is dynamic and must be resolved from the matching
`1b1c:0c57` device rather than hard-coded.

Suggested removal commands:

```bash
sudo rm /etc/udev/rules.d/70-nautilus-lcd.rules
sudo udevadm control --reload-rules
```

Reconnect the LCD USB device or reboot after removal.

The rule grants an ACL through systemd-logind to the active local session. It
does not make the device world-writable and does not grant access to other
Corsair or HID devices.
