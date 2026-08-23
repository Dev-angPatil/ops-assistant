# Arch Linux & Manjaro Knowledge & System Prompt Context

## 1. Distribution Profile
- **Family ID**: `arch`
- **Distributions**: Arch Linux, Manjaro, EndeavourOS, Garuda Linux, Artix (systemd variants).
- **Package Management**: Primary & Low-level: `pacman`. AUR helper: `yay` or `paru` (user context, never run with sudo).
- **Init System**: `systemd` (`systemctl`, `journalctl`).
- **Default Firewall**: `nftables` (`/etc/nftables.conf`, `nft`) or `iptables`/`ufw`.
- **Security Subsystem**: None by default (optional `AppArmor` or `SELinux`).
- **Network Configuration**: `systemd-networkd`, `NetworkManager`, or `iwd`.

## 2. Command Synthesis Guidelines & Hard Rules
1. **NO PARTIAL UPGRADES**: NEVER suggest `pacman -Sy <package>`. On Arch rolling release, syncing repositories without upgrading the entire system causes shared library breakage (ABI mismatch). Always use `sudo pacman -Syu --noconfirm` or `sudo pacman -S --needed <package>`.
2. **AUR Execution Rule**: NEVER run `sudo makepkg` or `sudo yay`. AUR builds must execute as an unprivileged user.
3. **Database Lock Handling**: If `/var/lib/pacman/db.lck` exists, check if pacman is running (`pgrep pacman`); if not running, remove the stale lock file `sudo rm -f /var/lib/pacman/db.lck`.
4. **Keyring Refresh**: If packages fail with `invalid or corrupted package (PGP signature)`, remediate with `sudo pacman -Sy --noconfirm archlinux-keyring && sudo pacman-key --refresh-keys`.

## 3. Key Filesystem & Configuration Map
- **Pacman Configuration**: `/etc/pacman.conf`.
- **Mirrorlist**: `/etc/pacman.d/mirrorlist` (managed with `reflector --latest 10 --sort rate --save /etc/pacman.d/mirrorlist`).
- **Initramfs Generation**: `/etc/mkinitcpio.conf` and `/etc/mkinitcpio.d/` (regenerate via `sudo mkinitcpio -P`).
- **Logs**:
  - Entirely stored in `systemd-journald` (`journalctl -xe`, `journalctl -u <service> -b`).
  - Pacman transactions: `/var/log/pacman.log`.
- **Bootloader**: `systemd-boot` (`/boot/loader/loader.conf`) or GRUB (`sudo grub-mkconfig -o /boot/grub/grub.cfg`).

## 4. Distro Quirks & Gotchas
- **Pacnew and Pacsave Files**: Upgrades never silently overwrite modified configuration files; they create `.pacnew` files (e.g. `/etc/pam.d/system-auth.pacnew`). Merge with `pacdiff`.
- **Bleeding Edge Kernel Updates**: Kernel updates overwrite `/usr/lib/modules/<version>/` immediately. If the system is not rebooted, loading new kernel modules will fail with `modprobe: FATAL: Module not found`.
- **No Pre-Enabled Services**: Installing packages does NOT enable or start systemd services. Always run `sudo systemctl enable --now <service>`.
