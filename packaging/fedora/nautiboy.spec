%global upstream_version 0.2.0.dev0

Name:           nautiboy
Version:        0.2.0~dev0
Release:        18%{?dist}
Summary:        Linux controller for Corsair NAUTILUS RS LCD displays

License:        GPL-3.0-or-later
URL:            https://github.com/NautiBoyLinux/nautiboy
Source0:        %{name}-%{upstream_version}.tar.gz

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
NautiBoy is an unofficial Linux application for controlling the LCD on the
hardware-tested Corsair Nautilus LCD Cap. It supports bounded static-image and
animated-GIF playback while preserving the controller's hardware-mode fallback.

%generate_buildrequires
%pyproject_buildrequires -x test

%prep
%autosetup -n %{name}-%{upstream_version}

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

for size in 16 32 48 64 128 256; do
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
%license LICENSE
%doc ATTRIBUTION.md CHANGELOG.md README.md
%doc docs/*.md
%{_bindir}/nautiboy
%{_datadir}/applications/io.github.nautiboylinux.nautiboy.desktop
%{_metainfodir}/io.github.nautiboylinux.nautiboy.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/io.github.nautiboylinux.nautiboy.png
%{_udevrulesdir}/70-nautilus-lcd.rules

%changelog
* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-18
- Add opt-in one-shot resume of the last successfully active display

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-17
- Persist only explicitly selected GIPHY media across application restarts

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-16
- Migrate to the secured io.github.nautiboylinux.nautiboy application identity

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-15
- Record successful physical Creative compositing validation

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-14
- Add Creative validation metrics and approved scrollable 760x960 interface

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-13
- Reuse experimental GIPHY search for Creative backgrounds

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-12
- Add Creative background, Orbit, and telemetry compositing preview

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-11
- Match the refined Orbit reference with larger type, layered arcs, and mascot divider

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-10
- Refine Orbit visuals and add measured backlog-free LCD scheduling

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-9
- Add the programmatic animated Orbit thermals preview and bounded scheduler

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-8
- Add read-only telemetry discovery and two-item Thermals configuration

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-7
- Add persistent renameable Creative presets for installed UI validation

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-6
- Add the v0.3 functional profile framework for installed UI validation

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-5
- Finalize secure GIPHY credentials and Preferences sizing validation

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-4
- Add secure desktop-keyring configuration for the experimental GIPHY provider

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-3
- Finalize Fedora lifecycle and namespace-validation documentation

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-2
- Declare root ownership explicitly for every packaged system file

* Fri Sep 04 2026 Andrew Tyler - 0.2.0~dev0-1
- Initial Fedora development package
