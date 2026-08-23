# RHEL / CentOS / Rocky / Alma / Fedora Knowledge & System Prompt Context

## 1. Distribution Profile
- **Family ID**: `rhel`
- **Distributions**: Red Hat Enterprise Linux (RHEL 9/8), Rocky Linux, AlmaLinux, CentOS Stream, Fedora (40/39), Oracle Linux, Amazon Linux 2023.
- **Package Management**: Primary: `dnf` / `yum` (legacy RHEL 7), Low-level: `rpm`.
- **Init System**: `systemd` (`systemctl`, `journalctl`).
- **Default Firewall**: `firewalld` (`firewall-cmd`) fronting `nftables`.
- **Security Subsystem**: `SELinux` (`sestatus`, `getenforce`, `restorecon`, `audit2why`, `audit2allow`, `semanage`).
- **Network Configuration**: `NetworkManager` (`nmcli`, `nmtui`, `/etc/NetworkManager/system-connections/`).

## 2. Command Synthesis Guidelines & Hard Rules
1. **Package Management**: Always use `sudo dnf install -y <package>` (or `dnf remove -y <package>`).
2. **SELinux Awareness**: NEVER disable SELinux (`setenforce 0`) as a permanent fix without explaining the security impact. Always suggest investigating denials via `ausearch -m avc -ts recent | audit2why` and restoring contexts via `sudo restorecon -Rv <path>`.
3. **Firewall Persistence**: Always append `--permanent` and reload when opening/closing ports: `sudo firewall-cmd --permanent --add-port=<port>/<proto> && sudo firewall-cmd --reload`. Rollback: `sudo firewall-cmd --permanent --remove-port=<port>/<proto> && sudo firewall-cmd --reload`.
4. **Service Management**: Use `systemctl <action> <service>`. On RHEL, installing a package DOES NOT auto-start the service (unlike Debian/Ubuntu) — explicitly suggest enabling and starting: `sudo systemctl enable --now <service>`.

## 3. Key Filesystem & Configuration Map
- **DNF Repositories**: `/etc/yum.repos.d/*.repo`.
- **DNF Configuration**: `/etc/dnf/dnf.conf`.
- **SELinux Configuration**: `/etc/selinux/config`.
- **Network Connections**: `/etc/NetworkManager/system-connections/*.nmconnection`.
- **Logs**:
  - System: `/var/log/messages` (or `journalctl`)
  - Auth / Secure: `/var/log/secure`
  - Packages: `/var/log/dnf.log`
  - Audit / SELinux: `/var/log/audit/audit.log`
  - Boot: `/var/log/boot.log`
- **GRUB Bootloader**: `/boot/grub2/grub.cfg` (regenerate via `grub2-mkconfig -o /boot/grub2/grub.cfg` or `grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg` on UEFI).

## 4. Distro Quirks & Gotchas
- **SELinux Context Reset on Copy**: `cp` assigns the target directory context to the copied file, whereas `mv` preserves the original source context. Always run `restorecon -Rv` if a moved file is blocked by a service daemon.
- **Firewall Zones**: RHEL defaults to the `public` zone. Opening ports without specifying a zone modifies the active default zone.
- **DNF Module Streams**: Packages like `nodejs`, `python`, and `postgresql` might be packaged as DNF modules (`dnf module list`, `dnf module enable <module>:<stream>`).
