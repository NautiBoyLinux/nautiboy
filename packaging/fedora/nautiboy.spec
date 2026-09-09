Name:           nautiboy
Version:        0.4.0~beta.1
Release:        1%{?dist}
Summary:        Linux controller for Corsair NAUTILUS RS LCD displays

License:        GPL-3.0-or-later AND CC-BY-SA-4.0
URL:            https://nautiboy.dev
Source0:        https://github.com/NautiBoyLinux/nautiboy/archive/v0.4.0-beta.1/%{name}-v0.4.0-beta.1.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  systemd-rpm-macros
Requires:       systemd-udev
Requires:       python3-keyring
Requires:       google-noto-sans-fonts

%description
NautiBoy is an unofficial Linux application for the hardware-tested Corsair
Nautilus LCD Cap. It provides static and animated media, read-only temperature
telemetry, and composited displays while preserving hardware-mode restoration.

%generate_buildrequires
%pyproject_buildrequires -x test

%prep
%autosetup -n %{name}-0.4.0-beta.1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files nautiboy

install -Dpm 0644 packaging/io.github.nautiboylinux.nautiboy.desktop \
    %{buildroot}%{_datadir}/applications/io.github.nautiboylinux.nautiboy.desktop
install -Dpm 0644 packaging/io.github.nautiboylinux.nautiboy.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.nautiboylinux.nautiboy.metainfo.xml
install -Dpm 0644 packaging/70-nautilus-lcd.rules \
    %{buildroot}%{_udevrulesdir}/70-nautilus-lcd.rules

for size in 16 32 48 64 128 256 512; do
    install -Dpm 0644 \
        packaging/icons/hicolor/${size}x${size}/apps/io.github.nautiboylinux.nautiboy.png \
        %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/io.github.nautiboylinux.nautiboy.png
done

%check
%pytest
desktop-file-validate packaging/io.github.nautiboylinux.nautiboy.desktop
appstreamcli validate --no-net packaging/io.github.nautiboylinux.nautiboy.metainfo.xml

%files -f %{pyproject_files}
%defattr(-,root,root,-)
%license LICENSE ARTWORK-LICENSE.txt
%doc ATTRIBUTION.md CHANGELOG.md README.md
%doc docs/*.md
%{_bindir}/nautiboy
%{_datadir}/applications/io.github.nautiboylinux.nautiboy.desktop
%{_metainfodir}/io.github.nautiboylinux.nautiboy.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/io.github.nautiboylinux.nautiboy.png
%{_udevrulesdir}/70-nautilus-lcd.rules

%changelog
* Sat Sep 05 2026 Andrew Tyler - 0.4.0~beta.1-1
- First public beta with media, telemetry, Creative compositing, and KDE integration
