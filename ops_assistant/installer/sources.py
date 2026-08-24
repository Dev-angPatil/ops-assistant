"""
Host source discovery, availability probe, and source ranking for the AI Installer.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ops_assistant.collectors.distro_detector import DistroDetector, DistroInfo
from ops_assistant.installer.models import InstallSource


@dataclass
class HostCapabilities:
    distro: DistroInfo
    has_pacman: bool = False
    has_yay: bool = False
    has_paru: bool = False
    has_apt: bool = False
    has_dnf: bool = False
    has_zypper: bool = False
    has_apk: bool = False
    has_flatpak: bool = False
    has_snap: bool = False
    has_pip: bool = False
    has_uv: bool = False
    has_npm: bool = False
    has_pnpm: bool = False
    has_yarn: bool = False
    has_bun: bool = False
    has_cargo: bool = False
    has_go: bool = False
    has_composer: bool = False
    has_dotnet: bool = False
    has_flutter: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distro_name": self.distro.distro_name,
            "distro_family": self.distro.family_id,
            "package_manager": self.distro.package_manager,
            "has_pacman": self.has_pacman,
            "has_yay": self.has_yay,
            "has_paru": self.has_paru,
            "has_apt": self.has_apt,
            "has_dnf": self.has_dnf,
            "has_zypper": self.has_zypper,
            "has_apk": self.has_apk,
            "has_flatpak": self.has_flatpak,
            "has_snap": self.has_snap,
            "has_pip": self.has_pip,
            "has_uv": self.has_uv,
            "has_npm": self.has_npm,
            "has_pnpm": self.has_pnpm,
            "has_yarn": self.has_yarn,
            "has_bun": self.has_bun,
            "has_cargo": self.has_cargo,
            "has_go": self.has_go,
            "has_composer": self.has_composer,
            "has_dotnet": self.has_dotnet,
            "has_flutter": self.has_flutter,
        }


class SourceResolver:
    """
    Probes available tools and ranks the optimal installation source.
    """

    @classmethod
    def probe_host(cls, distro_override: Optional[str] = None) -> HostCapabilities:
        detector = DistroDetector()
        d_info = detector.detect(override_family=distro_override)

        return HostCapabilities(
            distro=d_info,
            has_pacman=bool(shutil.which("pacman")),
            has_yay=bool(shutil.which("yay")),
            has_paru=bool(shutil.which("paru")),
            has_apt=bool(shutil.which("apt") or shutil.which("apt-get")),
            has_dnf=bool(shutil.which("dnf") or shutil.which("yum")),
            has_zypper=bool(shutil.which("zypper")),
            has_apk=bool(shutil.which("apk")),
            has_flatpak=bool(shutil.which("flatpak")),
            has_snap=bool(shutil.which("snap")),
            has_pip=bool(shutil.which("pip") or shutil.which("pip3")),
            has_uv=bool(shutil.which("uv")),
            has_npm=bool(shutil.which("npm")),
            has_pnpm=bool(shutil.which("pnpm")),
            has_yarn=bool(shutil.which("yarn")),
            has_bun=bool(shutil.which("bun")),
            has_cargo=bool(shutil.which("cargo")),
            has_go=bool(shutil.which("go")),
            has_composer=bool(shutil.which("composer")),
            has_dotnet=bool(shutil.which("dotnet")),
            has_flutter=bool(shutil.which("flutter")),
        )

    @classmethod
    def choose_best_source_for_app(
        cls,
        app_entry: Dict[str, Any],
        caps: HostCapabilities
    ) -> Tuple[InstallSource, str, str, Optional[str]]:
        """
        Determines the best available source and command for a catalog app.
        Returns: (InstallSource, source_label, install_command, rollback_command)
        """
        distro_fam = caps.distro.family_id
        packages = app_entry.get("packages", {})
        distro_pkgs = packages.get(distro_fam, {})

        # 1. Native Distribution Package (Arch pacman, Debian apt, Fedora dnf, SUSE zypper, Alpine apk)
        if distro_fam == "arch":
            if "pacman" in distro_pkgs:
                pkg = distro_pkgs["pacman"]
                return (
                    InstallSource.PACMAN,
                    f"Arch Linux ({caps.distro.package_manager})",
                    f"sudo pacman -S --needed --noconfirm {pkg}",
                    f"sudo pacman -Rns --noconfirm {pkg}"
                )
            elif "aur" in distro_pkgs:
                pkg = distro_pkgs["aur"]
                if caps.has_yay:
                    return (
                        InstallSource.YAY,
                        "Arch User Repository (yay)",
                        f"yay -S --needed --noconfirm {pkg}",
                        f"yay -Rns --noconfirm {pkg}"
                    )
                elif caps.has_paru:
                    return (
                        InstallSource.PARU,
                        "Arch User Repository (paru)",
                        f"paru -S --needed --noconfirm {pkg}",
                        f"paru -Rns --noconfirm {pkg}"
                    )
                elif caps.has_flatpak and app_entry.get("flatpak"):
                    fp_id = app_entry["flatpak"]
                    return (
                        InstallSource.FLATPAK,
                        "Flatpak (Flathub)",
                        f"flatpak install -y flathub {fp_id}",
                        f"flatpak uninstall -y {fp_id}"
                    )
                else:
                    # Fallback to yay with advisory
                    return (
                        InstallSource.YAY,
                        "Arch User Repository (AUR)",
                        f"which yay >/dev/null 2>&1 && yay -S --needed --noconfirm {pkg} || (echo 'Note: AUR package {pkg} requires yay/paru. Installing yay...' && sudo pacman -S --needed --noconfirm base-devel git && git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin && cd /tmp/yay-bin && makepkg -si --noconfirm && cd - && yay -S --needed --noconfirm {pkg})",
                        f"yay -Rns --noconfirm {pkg}"
                    )

        elif distro_fam in ("debian", "ubuntu", "boss"):
            if "apt" in distro_pkgs:
                pkg = distro_pkgs["apt"]
                return (
                    InstallSource.APT,
                    f"Debian/Ubuntu ({caps.distro.package_manager})",
                    f"sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}",
                    f"sudo apt-get remove -y {pkg}"
                )
            elif "deb_url" in distro_pkgs:
                url = distro_pkgs["deb_url"]
                tmp_deb = f"/tmp/{app_entry.get('name', 'app').lower().replace(' ', '_')}.deb"
                return (
                    InstallSource.DEB_FILE,
                    "Official Debian Package (.deb)",
                    f"curl -fsSL -o {tmp_deb} '{url}' && sudo apt install -y {tmp_deb} && rm -f {tmp_deb}",
                    f"sudo apt-get remove -y {app_entry.get('launch_cmd', 'app')}"
                )

        elif distro_fam in ("rhel", "fedora"):
            if "dnf" in distro_pkgs:
                pkg = distro_pkgs["dnf"]
                return (
                    InstallSource.DNF,
                    f"Fedora/RHEL ({caps.distro.package_manager})",
                    f"sudo dnf install -y {pkg}",
                    f"sudo dnf remove -y {pkg}"
                )

        elif distro_fam == "opensuse":
            if "zypper" in distro_pkgs:
                pkg = distro_pkgs["zypper"]
                return (
                    InstallSource.ZYPPER,
                    f"openSUSE ({caps.distro.package_manager})",
                    f"sudo zypper install -y {pkg}",
                    f"sudo zypper remove -y {pkg}"
                )

        elif distro_fam == "alpine":
            if "apk" in distro_pkgs:
                pkg = distro_pkgs["apk"]
                return (
                    InstallSource.APK,
                    f"Alpine Linux ({caps.distro.package_manager})",
                    f"sudo apk add {pkg}",
                    f"sudo apk del {pkg}"
                )

        # 2. Universal Flatpak (if available or specified)
        if app_entry.get("flatpak"):
            fp_id = app_entry["flatpak"]
            if caps.has_flatpak or "flatpak" in distro_pkgs:
                return (
                    InstallSource.FLATPAK,
                    "Flatpak (Flathub)",
                    f"flatpak install -y flathub {fp_id}",
                    f"flatpak uninstall -y {fp_id}"
                )

        # 3. Snap (if available)
        if app_entry.get("snap") and caps.has_snap:
            snap_pkg = app_entry["snap"]
            return (
                InstallSource.SNAP,
                "Snap Store",
                f"sudo snap install {snap_pkg}",
                f"sudo snap remove {snap_pkg.split()[0]}"
            )

        # 4. Fallback Generic
        launch = app_entry.get("launch_cmd", "package")
        return (
            InstallSource.PACMAN if distro_fam == "arch" else InstallSource.APT,
            f"System Package Manager ({caps.distro.package_manager})",
            f"sudo {caps.distro.package_manager} install -y {launch}",
            f"sudo {caps.distro.package_manager} remove -y {launch}"
        )
