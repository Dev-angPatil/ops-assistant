# Debian & Ubuntu Family Knowledge & System Prompt Context

## 1. Distribution Profile
- **Family ID**: `debian`
- **Distributions**: Ubuntu (24.04/22.04/20.04 LTS), Debian (12 Bookworm, 11 Bullseye), Linux Mint, Pop!_OS, Kali Linux, Raspberry Pi OS, BOSS Linux (Bharat Operating System Solutions).
- **Package Management**: Primary: `apt-get` (for scripting) / `apt` (interactive), Low-level: `dpkg`.
- **Init System**: `systemd` (`systemctl`, `journalctl`).
- **Default Firewall**: `ufw` (Uncomplicated Firewall) fronting `nftables`/`iptables`.
- **Security Subsystem**: `AppArmor` (`/etc/apparmor.d/`, `aa-status`, `aa-enforce`, `aa-complain`).
- **Network Configuration**: `netplan` (`/etc/netplan/*.yaml` with `netplan apply`) on Ubuntu; `/etc/network/interfaces` or `NetworkManager` on Debian.

## 2. Command Synthesis Guidelines & Hard Rules
1. **Scripting Non-Interactivity**: Always use `DEBIAN_FRONTEND=noninteractive apt-get install -y <package>` to prevent terminal hanging on debconf questions.
2. **Never suggest raw `apt` in automated scripts**: Always prefer `apt-get` for deterministic stdout without CLI stability warnings.
3. **Service Management**: Always use `systemctl <action> <service>` (e.g. `sudo systemctl restart nginx`). Rollback: inverse `systemctl` action.
4. **Firewall Rules**: Always use `sudo ufw allow <port>/<proto>` and `sudo ufw reload`. Rollback: `sudo ufw delete allow <port>/<proto>`.
5. **Never delete lock files blindly**: If `/var/lib/dpkg/lock-frontend` is locked, inspect active lockers first (`fuser -vk /var/lib/dpkg/lock-frontend`), stop `unattended-upgrades`, and only remove if stale.

## 3. Key Filesystem & Configuration Map
- **APT Sources**: `/etc/apt/sources.list`, `/etc/apt/sources.list.d/*.sources` (deb822 format in 24.04+) or `*.list`.
- **APT Preferences**: `/etc/apt/preferences.d/` (package pinning).
- **Netplan Configs**: `/etc/netplan/*.yaml`.
- **Logs**:
  - System: `/var/log/syslog` (or `journalctl -p 0..4`)
  - Auth: `/var/log/auth.log`
  - Packages: `/var/log/dpkg.log`
  - Kernel: `/var/log/kern.log`
  - AppArmor: `/var/log/audit/audit.log` or `/var/log/syslog` or `journalctl -k`
- **DNS Resolver**: `/etc/systemd/resolved.conf` and `resolvectl status` (symlinked `/etc/resolv.conf`).
- **Default Editor/Alternatives**: `update-alternatives --config <name>`.

## 4. Distro Quirks & Gotchas
- **PEP 668 (Externally Managed Environment)**: On Debian 12+ and Ubuntu 23.04+, system-wide `pip install` is blocked. Use `python3 -m venv` or `--break-system-packages` only when explicitly requested.
- **Deb822 Sources Format**: Ubuntu 24.04 uses `/etc/apt/sources.list.d/ubuntu.sources` instead of classic `/etc/apt/sources.list`.
- **Service Auto-Start on Install**: Debian/Ubuntu automatically starts and enables services immediately after `apt-get install`. If a service needs config before starting, handle the initial start failure cleanly.
- **Unattended-Upgrades Lock Collision**: Boot-time `apt` operations frequently fail due to `unattended-upgr` holding `/var/lib/dpkg/lock-frontend`.
