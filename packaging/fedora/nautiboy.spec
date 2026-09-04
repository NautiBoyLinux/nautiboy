%global upstream_version 0.2.0.dev0

Name:           nautiboy
Version:        0.2.0~dev0
Release:        5%{?dist}
Summary:        Linux controller for Corsair NAUTILUS RS LCD displays

License:        GPL-3.0-or-later
URL:            https://github.com/nautiboy/nautiboy
Source0:        %{name}-%{upstream_version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  systemd-rpm-macros
Requires:       systemd-udev
Requires:       python3-keyring

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

install -Dpm 0644 packaging/io.github.nautiboy.nautiboy.desktop \
    %{buildroot}%{_datadir}/applications/io.github.nautiboy.nautiboy.desktop
install -Dpm 0644 packaging/io.github.nautiboy.nautiboy.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.nautiboy.nautiboy.metainfo.xml
install -Dpm 0644 packaging/70-nautilus-lcd.rules \
    %{buildroot}%{_udevrulesdir}/70-nautilus-lcd.rules

for size in 16 32 48 64 128 256; do
    install -Dpm 0644 \
        packaging/icons/hicolor/${size}x${size}/apps/io.github.nautiboy.nautiboy.png \
        %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/io.github.nautiboy.nautiboy.png
done

%check
%pytest
desktop-file-validate packaging/io.github.nautiboy.nautiboy.desktop
appstreamcli validate --no-net packaging/io.github.nautiboy.nautiboy.metainfo.xml

%files -f %{pyproject_files}
%defattr(-,root,root,-)
%license LICENSE
%doc ATTRIBUTION.md CHANGELOG.md README.md
%doc docs/*.md
%{_bindir}/nautiboy
%{_datadir}/applications/io.github.nautiboy.nautiboy.desktop
%{_metainfodir}/io.github.nautiboy.nautiboy.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/io.github.nautiboy.nautiboy.png
%{_udevrulesdir}/70-nautilus-lcd.rules

%changelog
* Fri Sep 04 2026 Andrew Tyler <apaultyler92@gmail.com> - 0.2.0~dev0-5
- Finalize secure GIPHY credentials and Preferences sizing validation

* Fri Sep 04 2026 Andrew Tyler <apaultyler92@gmail.com> - 0.2.0~dev0-4
- Add secure desktop-keyring configuration for the experimental GIPHY provider

* Fri Sep 04 2026 Andrew Tyler <apaultyler92@gmail.com> - 0.2.0~dev0-3
- Finalize Fedora lifecycle and namespace-validation documentation

* Fri Sep 04 2026 Andrew Tyler <apaultyler92@gmail.com> - 0.2.0~dev0-2
- Declare root ownership explicitly for every packaged system file

* Fri Sep 04 2026 Andrew Tyler <apaultyler92@gmail.com> - 0.2.0~dev0-1
- Initial Fedora development package
