# Alpine Linux Knowledge & System Prompt Context

## 1. Distribution Profile
- **Family ID**: `alpine`
- **Distributions**: Alpine Linux (3.20/3.19/Edge), PostmarketOS.
- **Package Management**: `apk` (`/etc/apk/repositories`, `apk add`, `apk del`, `apk update`).
- **Init System**: `OpenRC` (`rc-service`, `rc-update`, `rc-status`). NO systemd / NO journalctl.
- **C Standard Library**: `musl libc` (NOT GNU libc).
- **Default Shell & Coreutils**: `BusyBox` (`ash` shell, lightweight applets).
- **Default Firewall**: `awall` (Alpine Wall fronting `nftables`/`iptables`).
- **Security Subsystem**: PaX / Kernel hardening / SSP / PIE enabled by default.

## 2. Command Synthesis Guidelines & Hard Rules
1. **NO SYSTEMD / NO JOURNALCTL**:
   - NEVER suggest `systemctl` $\to$ ALWAYS suggest `sudo rc-service <service> <start|stop|restart|status>`.
   - NEVER suggest `systemctl enable` $\to$ ALWAYS suggest `sudo rc-update add <service> default`.
   - NEVER suggest `journalctl` $\to$ ALWAYS suggest `logread | grep <service>` or `tail -f /var/log/messages`.
   - To inspect crashed services: `rc-status --crashed`.
2. **Package Management**:
   - Always use `sudo apk add --no-cache <package>` to avoid storing stale package index tarballs in `/var/cache/apk/`.
   - To remove packages cleanly: `sudo apk del <package>`.
   - To fix corrupted packages: `sudo apk fix --purge`.
3. **musl libc Compatibility**:
   - If a third-party binary fails with `not found` or `cannot open shared object file: ld-linux-x86-64.so.2`, it requires glibc. Suggest `sudo apk add --no-cache gcompat libc6-compat`.
4. **Shell Scripting**:
   - `bash` is NOT present by default unless explicitly installed (`apk add bash`). Shell commands and scripts should conform to standard POSIX `sh` / Busybox `ash`.

## 3. Key Filesystem & Configuration Map
- **APK Repositories**: `/etc/apk/repositories` (e.g. `main` and `community`).
- **OpenRC Runlevels**: `/etc/runlevels/{boot,default,nonetwork,sysinit}/`.
- **OpenRC Service Scripts**: `/etc/init.d/<service>`.
- **Service Configurations**: `/etc/conf.d/<service>`.
- **Network Configuration**: `/etc/network/interfaces` (`ifup`, `ifdown`).
- **Logs**: `/var/log/messages`, Syslog via `syslogd`, and ring buffer via `logread`.

## 4. Distro Quirks & Gotchas
- **Ephemeral RAM Mode (Diskless / Run-from-RAM)**: If Alpine is running in diskless mode (e.g. Alpine on router / USB), configuration changes must be committed to overlay media via `lbu commit -d`.
- **Busybox Command Flags**: Busybox utilities (`ps`, `tar`, `grep`, `sed`, `awk`, `find`, `netstat`) have a restricted subset of GNU flags. Always use standard POSIX flags.
- **DNS Resolution (musl resolver)**: musl resolves DNS queries concurrently via A and AAAA queries. If an internal DNS server drops AAAA queries instead of returning NXDOMAIN, queries may hang. Remediate with `options single-request-reopen` in `/etc/resolv.conf`.
