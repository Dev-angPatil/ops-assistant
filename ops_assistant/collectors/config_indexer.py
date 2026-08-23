"""
User Configuration Indexer — Scans and catalogs active desktop and system configuration files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class UserConfigIndexer:
    """Discovers and maps user and system configuration files across Linux desktop environments."""

    COMMON_CONFIG_TARGETS = [
        # Window Managers / Compositors
        ("hyprland", "~/.config/hypr/hyprland.conf", "Hyprland main compositor configuration file"),
        ("hyprland_lua", "~/.config/hypr/hyprland.lua", "Hyprland main compositor configuration file (Lua / HyDE)"),
        ("hypridle", "~/.config/hypr/hypridle.conf", "Hyprland idle daemon configuration"),
        ("hyprlock", "~/.config/hypr/hyprlock.conf", "Hyprland screen locker configuration"),
        ("hyprpaper", "~/.config/hypr/hyprpaper.conf", "Hyprpaper wallpaper daemon configuration"),
        ("sway", "~/.config/sway/config", "Sway Wayland compositor configuration"),
        ("i3", "~/.config/i3/config", "i3 window manager configuration"),
        ("kde_globals", "~/.config/kdeglobals", "KDE Plasma global desktop settings"),

        # Status Bars & Launchers
        ("waybar", "~/.config/waybar/config", "Waybar status bar layout configuration"),
        ("waybar_jsonc", "~/.config/waybar/config.jsonc", "Waybar JSONC layout configuration"),
        ("waybar_style", "~/.config/waybar/style.css", "Waybar CSS styling stylesheet"),
        ("rofi", "~/.config/rofi/config.rasi", "Rofi application launcher configuration"),
        ("wofi", "~/.config/wofi/config", "Wofi application launcher configuration"),
        ("dunst", "~/.config/dunst/dunstrc", "Dunst notification daemon configuration"),
        ("mako", "~/.config/mako/config", "Mako notification daemon configuration"),

        # Terminals & Editors
        ("kitty", "~/.config/kitty/kitty.conf", "Kitty terminal emulator configuration"),
        ("alacritty", "~/.config/alacritty/alacritty.toml", "Alacritty terminal emulator configuration"),
        ("ghostty", "~/.config/ghostty/config", "Ghostty terminal emulator configuration"),
        ("foot", "~/.config/foot/foot.ini", "Foot Wayland terminal configuration"),
        ("neovim", "~/.config/nvim/init.lua", "Neovim editor Lua configuration"),
        ("tmux", "~/.tmux.conf", "Tmux terminal multiplexer configuration"),

        # Shells & Environment
        ("zsh", "~/.zshrc", "Zsh interactive shell configuration"),
        ("bash", "~/.bashrc", "Bash interactive shell configuration"),
        ("profile", "~/.profile", "User environment login profile"),
        ("fish", "~/.config/fish/config.fish", "Fish shell configuration"),

        # System Files
        ("fstab", "/etc/fstab", "Filesystem mount table configuration"),
        ("hosts", "/etc/hosts", "Static IP-to-hostname mappings"),
        ("resolv", "/etc/resolv.conf", "DNS resolver configuration"),
        ("environment", "/etc/environment", "System-wide environment variables"),
    ]

    @classmethod
    def scan_active_configs(cls) -> List[Dict[str, Any]]:
        """Scans the local filesystem for all existing active configuration files."""
        results: List[Dict[str, Any]] = []
        seen_paths = set()

        for key, raw_path, desc in cls.COMMON_CONFIG_TARGETS:
            expanded = Path(os.path.expanduser(raw_path)).resolve()
            if expanded.exists() and expanded.is_file() and str(expanded) not in seen_paths:
                try:
                    stat = expanded.stat()
                    results.append({
                        "config_key": key,
                        "raw_path": raw_path,
                        "absolute_path": str(expanded),
                        "description": desc,
                        "size_bytes": stat.st_size,
                        "modified_time": stat.st_mtime
                    })
                    seen_paths.add(str(expanded))
                except Exception:
                    continue

        return results
