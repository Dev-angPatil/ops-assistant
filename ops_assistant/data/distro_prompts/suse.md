# openSUSE & SUSE Linux Enterprise (SLES) Knowledge & System Prompt Context

## 1. Distribution Profile
- **Family ID**: `suse`
- **Distributions**: openSUSE Tumbleweed (Rolling), openSUSE Leap (15.5/15.6), SUSE Linux Enterprise Server (SLES 15), openSUSE MicroOS / Aeon / Kalpa (Immutable).
- **Package Management**: Primary: `zypper` (high-level SAT solver engine), Low-level: `rpm`. YaST tool suite (`yast2`).
- **Init System**: `systemd` (`systemctl`, `journalctl`).
- **Default Filesystem**: `Btrfs` with `Snapper` automated pre/post snapshot rollback.
- **Default Firewall**: `firewalld` (`firewall-cmd`) or legacy `SuSEfirewall2`.
- **Security Subsystem**: `AppArmor` (`aa-status`, `aa-enforce`, `/etc/apparmor.d/`).
- **Network Configuration**: `wicked` (`wicked ifup`, `/etc/wicked/`) on Leap/SLES, or `NetworkManager` on Tumbleweed.

## 2. Command Synthesis Guidelines & Hard Rules
1. **Non-Interactive Scripting**: Always pass `--non-interactive` (or `-n`) with `zypper` to prevent interactive prompts from blocking:
   - Install: `sudo zypper --non-interactive install <package>` (or `sudo zypper -n in <package>`).
   - Remove: `sudo zypper --non-interactive remove --clean-deps <package>` (or `sudo zypper -n rm -u <package>`).
   - Refresh: `sudo zypper refresh` (or `sudo zypper ref`).
   - System Upgrade: `sudo zypper --non-interactive dup` (on Tumbleweed) or `sudo zypper --non-interactive update` (on Leap).
2. **Lock Handling (PackageKit collision)**: `zypper` locks `/var/run/zypp.pid`. If blocked by PackageKit daemon, stop it with `sudo systemctl stop packagekit` before running zypper commands.
3. **Btrfs & Snapper Snapshots**:
   - If disk space is unexpectedly full, check btrfs snapshots: `sudo snapper list` and clean old snapshots: `sudo snapper cleanup number`.
   - To roll back a bad system modification: `sudo snapper rollback <snapshot_id>`.
4. **Network Service Management (Wicked vs NetworkManager)**:
   - On openSUSE/SLES servers running `wicked`: `sudo wicked ifstatus all` and `sudo wicked ifreload all`.

## 3. Key Filesystem & Configuration Map
- **Zypper Repositories**: `/etc/zypp/repos.d/*.repo`.
- **Zypper Configuration**: `/etc/zypp/zypp.conf`.
- **Wicked Network Configuration**: `/etc/wicked/config.xml` and `/etc/sysconfig/network/ifcfg-*`.
- **Snapper Configuration**: `/etc/snapper/configs/root`.
- **Logs**:
  - System: `/var/log/messages` (or `journalctl`)
  - Zypper: `/var/log/zypper.log`
  - YaST: `/var/log/YaST2/y2log`
  - Firewall/Security: `/var/log/audit/audit.log` or `/var/log/messages`
- **Bootloader**: `update-bootloader --refresh` or `grub2-mkconfig -o /boot/grub2/grub.cfg`.

## 4. Distro Quirks & Gotchas
- **YaST Overwrite**: Configuration files managed by YaST (like `/etc/sysconfig/*`) may be overwritten by YaST modules during system management tasks.
- **Repository Vendor Sticky Bit**: By default, `zypper` refuses to switch package vendor (e.g. from openSUSE to Packman) unless `--allow-vendor-change` is explicitly passed.
- **MicroOS / Immutable Distros**: On openSUSE MicroOS, the root filesystem `/` is read-only. Package changes must be done via `transactional-update pkg in <package>` followed by a reboot.
