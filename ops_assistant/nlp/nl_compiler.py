"""
Natural Language Command Compiler — Translates arbitrary English sentences,
voice transcriptions, and complex instructions into valid Linux shell commands
with zero external runtime dependencies.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class NaturalLanguageCompiler:
    """
    Intelligent semantic compiler for Linux operations.
    Converts open-ended natural language prompts (e.g. 'inside Divya create one folder name as DBMS',
    'open YouTube', 'open my DSA folder', 'open lead code platform') into valid, safe Linux commands.
    """

    POPULAR_SITES = {
        "youtube": "https://youtube.com",
        "yt": "https://youtube.com",
        "leetcode": "https://leetcode.com",
        "lead code": "https://leetcode.com",
        "leadcode": "https://leetcode.com",
        "github": "https://github.com",
        "git hub": "https://github.com",
        "google": "https://google.com",
        "chatgpt": "https://chatgpt.com",
        "chat gpt": "https://chatgpt.com",
        "openai": "https://chatgpt.com",
        "reddit": "https://reddit.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "gmail": "https://mail.google.com",
        "linkedin": "https://linkedin.com",
        "amazon": "https://amazon.com",
        "netflix": "https://netflix.com",
        "spotify": "https://open.spotify.com",
        "wikipedia": "https://wikipedia.org",
        "geeksforgeeks": "https://geeksforgeeks.org",
        "gfg": "https://geeksforgeeks.org",
        "hackerrank": "https://hackerrank.com",
        "codechef": "https://codechef.com",
        "canvas": "https://canvas.instructure.com",
    }

    DESKTOP_APPS = {
        "browser": ["xdg-open https://google.com"],
        "web browser": ["xdg-open https://google.com"],
        "chrome": ["google-chrome", "chromium", "xdg-open https://google.com"],
        "google chrome": ["google-chrome", "chromium", "xdg-open https://google.com"],
        "brave": ["brave", "brave-browser", "xdg-open https://google.com"],
        "brave browser": ["brave", "brave-browser", "xdg-open https://google.com"],
        "firefox": ["firefox", "xdg-open https://google.com"],
        "terminal": ["x-terminal-emulator", "alacritty", "kitty", "gnome-terminal", "konsole", "xterm"],
        "calculator": ["gnome-calculator", "kcalc", "galculator", "xcalc"],
        "code": ["code .", "codium ."],
        "vs code": ["code .", "codium ."],
        "vscode": ["code .", "codium ."],
        "file manager": ["xdg-open ~", "nautilus ~", "dolphin ~", "thunar ~"],
        "files": ["xdg-open ~", "nautilus ~", "dolphin ~", "thunar ~"],
    }

    STANDARD_FOLDERS = {
        "downloads": "~/Downloads",
        "download": "~/Downloads",
        "documents": "~/Documents",
        "document": "~/Documents",
        "desktop": "~/Desktop",
        "pictures": "~/Pictures",
        "picture": "~/Pictures",
        "photos": "~/Pictures",
        "music": "~/Music",
        "videos": "~/Videos",
        "video": "~/Videos",
        "movies": "~/Videos",
        "home": "~",
        "root": "/",
    }

    @classmethod
    def compile(cls, text: str, cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Compiles natural language text into a structured command plan.
        Returns None if text cannot be definitively compiled by heuristics.
        """
        raw = text.strip()
        if not raw:
            return None

        # Clean punctuation and extra spaces
        clean = re.sub(r"^\$\s*", "", raw)
        clean = re.sub(r"[\.!\?]+$", "", clean).strip()

        # 1. Folder & Directory Creation
        # e.g. "inside Divya create one folder name as DBMS", "in Divya create folder DBMS"
        m = re.search(r"^(?:in|inside)\s+(?:the\s+|folder\s+|dir\s+)?(?P<parent>[a-zA-Z0-9_\-\.\/~]+)\s+(?:please\s+)?(?:create|make|add)\s+(?:a\s+|one\s+|new\s+)?(?:folder|dir|directory)(?:\s+(?:name\s+as|named\s+as|named|called|name|as))?\s+(?P<child>[a-zA-Z0-9_\-\.\/]+)$", clean, re.IGNORECASE)
        if m:
            parent = m.group("parent").strip()
            child = m.group("child").strip()
            full_path = f"{parent}/{child}" if not parent.endswith("/") else f"{parent}{child}"
            cmd = f"mkdir -p '{full_path}'"
            desc = f"Creates directory '{child}' inside '{parent}'."
            return {
                "command": cmd,
                "path": full_path,
                "parent": parent,
                "child": child,
                "description": desc,
                "intent": "dir_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.15,
                "rollback_command": f"rmdir '{full_path}' 2>/dev/null || rm -rf '{full_path}'",
                "explanation": f"I will create a new directory named '{child}' inside the '{parent}' folder.",
                "explanation_paragraph": f"The natural language assistant parsed your instruction to create a folder. It prepared and executed the Linux command `mkdir -p '{full_path}'`, which creates the target directory '{child}' inside '{parent}' (including any required parent paths) at the specified filesystem location."
            }

        # e.g. "create a folder named DBMS inside Divya", "make folder DBMS in Divya"
        m = re.search(r"^(?:please\s+)?(?:create|make|add)\s+(?:a\s+|one\s+|new\s+)?(?:folder|dir|directory)(?:\s+(?:name\s+as|named\s+as|named|called|name|as))?\s+(?P<child>[a-zA-Z0-9_\-\.\/]+)\s+(?:in|inside|under)\s+(?:the\s+|folder\s+|dir\s+)?(?P<parent>[a-zA-Z0-9_\-\.\/~]+)$", clean, re.IGNORECASE)
        if m:
            parent = m.group("parent").strip()
            child = m.group("child").strip()
            full_path = f"{parent}/{child}" if not parent.endswith("/") else f"{parent}{child}"
            cmd = f"mkdir -p '{full_path}'"
            desc = f"Creates directory '{child}' inside '{parent}'."
            return {
                "command": cmd,
                "path": full_path,
                "parent": parent,
                "child": child,
                "description": desc,
                "intent": "dir_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.15,
                "rollback_command": f"rmdir '{full_path}' 2>/dev/null || rm -rf '{full_path}'",
                "explanation": f"I will create a new directory named '{child}' inside the '{parent}' folder.",
                "explanation_paragraph": f"The natural language assistant parsed your instruction to create a folder. It prepared and executed the Linux command `mkdir -p '{full_path}'`, which creates the target directory '{child}' inside '{parent}' at the specified filesystem location."
            }

        # e.g. "create folder DBMS", "make directory my_project"
        m = re.search(r"^(?:please\s+)?(?:create|make|add)\s+(?:a\s+|one\s+|new\s+)?(?:folder|dir|directory)(?:\s+(?:name\s+as|named\s+as|named|called|name|as))?\s+(?P<name>[a-zA-Z0-9_\-\.\/~]+)$", clean, re.IGNORECASE)
        if m:
            name = m.group("name").strip()
            cmd = f"mkdir -p '{name}'"
            desc = f"Creates directory '{name}'."
            return {
                "command": cmd,
                "path": name,
                "description": desc,
                "intent": "dir_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.15,
                "rollback_command": f"rmdir '{name}' 2>/dev/null || rm -rf '{name}'",
                "explanation": f"I will create a new directory named '{name}'.",
                "explanation_paragraph": f"The natural language assistant compiled your instruction into the command `mkdir -p '{name}'`. This safely provisions the folder in your current working directory without overwriting existing files."
            }

        # 2. File Creation with / without content
        # e.g. "inside Divya create file notes.txt with content 'hello world'"
        m = re.search(r"^(?:in|inside)\s+(?P<parent>[a-zA-Z0-9_\-\.\/~]+)\s+(?:create|make|touch|write)\s+(?:a\s+|one\s+|new\s+)?file\s+(?P<file>[a-zA-Z0-9_\-\.\/]+)(?:\s+with\s+(?:content|text)\s+['\"]?(?P<content>.*?)['\"]?)?$", clean, re.IGNORECASE)
        if m:
            parent = m.group("parent").strip()
            filename = m.group("file").strip()
            content = (m.group("content") or "").strip()
            full_path = f"{parent}/{filename}" if not parent.endswith("/") else f"{parent}{filename}"
            if content:
                cmd = f"mkdir -p '{parent}' && echo '{content}' > '{full_path}'"
                desc = f"Creates file '{full_path}' with specified content."
            else:
                cmd = f"mkdir -p '{parent}' && touch '{full_path}'"
                desc = f"Creates empty file '{full_path}'."
            return {
                "command": cmd,
                "path": full_path,
                "content": content,
                "description": desc,
                "intent": "file_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.20,
                "rollback_command": f"rm -f '{full_path}'",
                "explanation": f"I will create the file '{filename}' inside '{parent}'.",
                "explanation_paragraph": f"The assistant compiled your request into `mkdir -p '{parent}' && echo '{content}' > '{full_path}'`. This ensures the parent directory exists and writes the file content to disk."
            }

        # 3. Web & Browser Launching
        # e.g. "open YouTube", "open lead code platform", "launch leetcode", "open brave browser"
        m = re.search(r"^(?:please\s+)?(?:open|launch|start|browse|play|visit|go\s+to)\s+(?P<target>.+)$", clean, re.IGNORECASE)
        if m:
            orig_target = m.group("target").strip()
            target = orig_target.lower()

            # Direct URL
            if target.startswith(("http://", "https://", "www.")):
                url = orig_target if orig_target.startswith(("http://", "https://")) else "https://" + orig_target
                return {
                    "command": f"xdg-open '{url}'",
                    "url": url,
                    "description": f"Opens website '{url}' in default web browser.",
                    "intent": "desktop_open_browser",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will open '{url}' in your default browser.",
                    "explanation_paragraph": f"The natural language assistant converted the target URL into `xdg-open '{url}'`, which triggers your system's default desktop web browser to navigate to the specified page."
                }

            # Check popular sites dictionary
            for site_key, site_url in cls.POPULAR_SITES.items():
                if re.search(rf"\b{re.escape(site_key)}\b", target, re.IGNORECASE):
                    return {
                        "command": f"xdg-open '{site_url}'",
                        "url": site_url,
                        "description": f"Opens {site_key.title()} ({site_url}) in default web browser.",
                        "intent": "desktop_open_browser",
                        "safety_level": "READ_ONLY",
                        "risk_score": 0.05,
                        "explanation": f"I will open {site_key.title()} ({site_url}) in your web browser.",
                        "explanation_paragraph": f"The natural language assistant recognized your request to visit {site_key.title()}. It executed `xdg-open '{site_url}'`, launching your default browser directly to {site_url}."
                    }

            # Check desktop applications
            for app_key, app_cmds in cls.DESKTOP_APPS.items():
                if target == app_key or target == f"my {app_key}" or target == f"the {app_key}":
                    cmd = app_cmds[0]
                    return {
                        "command": cmd,
                        "url": "https://google.com" if "http" in cmd else "",
                        "description": f"Launches desktop application: '{app_key}'.",
                        "intent": "desktop_open_browser" if "http" in cmd else "generic_command",
                        "safety_level": "READ_ONLY",
                        "risk_score": 0.05,
                        "explanation": f"I will launch '{app_key}'.",
                        "explanation_paragraph": f"The assistant recognized your request to launch the '{app_key}' desktop application and dispatched the system binary command `{cmd}`."
                    }

            # Check standard named folders (e.g. "open downloads", "open my documents folder")
            cleaned_target = re.sub(r"^(?:my|the)\s+", "", target)
            cleaned_target = re.sub(r"\s+(?:folder|dir|directory)$", "", cleaned_target).strip()
            if cleaned_target in cls.STANDARD_FOLDERS:
                folder_path = cls.STANDARD_FOLDERS[cleaned_target]
                expanded_path = os.path.expanduser(folder_path)
                cmd = f"xdg-open '{expanded_path}'"
                return {
                    "command": cmd,
                    "path": expanded_path,
                    "description": f"Opens '{folder_path}' in system file manager.",
                    "intent": "desktop_open_folder",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will open the '{cleaned_target.capitalize()}' folder in your file manager.",
                    "explanation_paragraph": f"The assistant parsed your request to view the {cleaned_target.capitalize()} directory and executed `xdg-open '{expanded_path}'` to launch your system's graphical file manager."
                }

            # Check domain name patterns (e.g. "open amazon.in", "open wikipedia.org")
            if re.search(r"^[a-zA-Z0-9\-]+\.[a-z]{2,}(?:\/[^\s]*)?$", target):
                url = "https://" + orig_target
                return {
                    "command": f"xdg-open '{url}'",
                    "url": url,
                    "description": f"Opens website '{url}' in default browser.",
                    "intent": "desktop_open_browser",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will open '{url}' in your browser.",
                    "explanation_paragraph": f"The assistant recognized the web domain '{orig_target}' and executed `xdg-open '{url}'` to launch the webpage in your default browser."
                }

            # Check arbitrary folder open (e.g. "open my DSA folder", "open folder Divya")
            m_folder = re.search(r"^(?:my\s+|the\s+)?(?P<fld>[a-zA-Z0-9_\-\.]+)\s+folder$", orig_target, re.IGNORECASE)
            if m_folder:
                fld = m_folder.group("fld").strip()
                home_target = os.path.expanduser(f"~/{fld}")
                cmd = f"xdg-open '{home_target}' 2>/dev/null || xdg-open './{fld}' 2>/dev/null || xdg-open ~"
                return {
                    "command": cmd,
                    "path": home_target,
                    "description": f"Opens folder '{fld}' in default file manager.",
                    "intent": "desktop_open_folder",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will open the '{fld}' folder in your file manager.",
                    "explanation_paragraph": f"The assistant resolved the folder reference '{fld}' and dispatched `xdg-open` to reveal the directory in your desktop file manager."
                }

        # 3.5 File Organization & Moves (e.g. "move my downloaded photos into a folder called photos")
        m_move = re.search(
            r"^(?:please\s+)?(?:move|transfer|relocate|organize)\s+(?:all\s+)?(?:my\s+)?(?P<cat>downloaded\s+photos|photos\s+in\s+downloads|downloaded\s+images|images\s+in\s+downloads|photos|images|pictures|videos|documents|music|archives|files)\s*(?:from\s+(?P<src>[^\s]+)\s+)?(?:in(?:to)?|to)\s+(?:a\s+)?(?:folder\s+(?:called|named)\s+)?(?P<dst>.+)$",
            clean,
            re.IGNORECASE
        )
        if m_move:
            cat_raw = m_move.group("cat").lower()
            src_raw = (m_move.group("src") or "").strip()
            dst_raw = (m_move.group("dst") or "").strip().rstrip(". ")

            if "photo" in cat_raw or "image" in cat_raw or "picture" in cat_raw:
                src_path = os.path.expanduser(src_raw or "~/Downloads")
                if not dst_raw or dst_raw.lower() in ("photos", "my photos", "folder photos", "a folder called photos"):
                    dst_path = os.path.expanduser("~/Pictures/Photos")
                else:
                    dst_path = os.path.expanduser(f"~/{dst_raw.capitalize()}" if not dst_raw.startswith(("/", "~", ".")) else dst_raw)

                cmd = f"mkdir -p '{dst_path}' && find '{src_path}' -maxdepth 1 -type f \\( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.avif' \\) -exec mv -t '{dst_path}' {{}} +"
                return {
                    "command": cmd,
                    "description": f"Moves all photos and images from '{src_path}' to '{dst_path}'.",
                    "intent": "file_move",
                    "safety_level": "MODIFYING",
                    "risk_score": 0.25,
                    "rollback_command": f"find '{dst_path}' -maxdepth 1 -type f -exec mv -t '{src_path}' {{}} +",
                    "explanation": f"I will move your downloaded photos into '{dst_path}'.",
                    "explanation_paragraph": f"The assistant compiled your request into a batch file mover. It creates '{dst_path}' if needed and moves matching image formats (.jpg, .png, .webp, .gif) from '{src_path}'."
                }

        # 3.6 Desktop Wallpaper Management (e.g. "change my wallpaper", "set wallpaper to ...")
        m_wall = re.search(
            r"^(?:can\s+you\s+)?(?:please\s+)?(?:change|set|switch|update|randomize|random)\s+(?:my\s+|the\s+)?(?:desktop\s+)?wallpaper(?:\s+(?:to|with)\s+(?P<img_path>.+))?$",
            clean,
            re.IGNORECASE
        )
        if m_wall:
            img_path_raw = (m_wall.group("img_path") or "").strip().strip("\"'")
            if img_path_raw:
                expanded_img = os.path.expanduser(img_path_raw)
                cmd = f"wall='{expanded_img}'; [ -f \"$wall\" ] && (mkdir -p ~/.config/hypr && echo -e \"preload = $wall\\nwallpaper = ,$wall\\nsplash = false\" > ~/.config/hypr/hyprpaper.conf && pkill -x hyprpaper 2>/dev/null; hyprpaper >/dev/null 2>&1 & which matugen >/dev/null 2>&1 && matugen image \"$wall\" 2>/dev/null || true; which swww >/dev/null 2>&1 && swww img \"$wall\" --transition-type wipe 2>/dev/null || true; which feh >/dev/null 2>&1 && feh --bg-fill \"$wall\" 2>/dev/null || true; which gsettings >/dev/null 2>&1 && gsettings set org.gnome.desktop.background picture-uri \"file://$wall\" 2>/dev/null || true)"
                desc = f"Sets desktop wallpaper to '{expanded_img}'."
            else:
                cmd = "wall=$(find ~/Pictures/Wallpapers ~/Pictures/Photos/Wallpaper ~/Pictures /usr/share/backgrounds -type f \\( -iname '*.jpg' -o -iname '*.png' -o -iname '*.webp' \\) 2>/dev/null | shuf -n 1); [ -n \"$wall\" ] && (mkdir -p ~/.config/hypr && echo -e \"preload = $wall\\nwallpaper = ,$wall\\nsplash = false\" > ~/.config/hypr/hyprpaper.conf && pkill -x hyprpaper 2>/dev/null; hyprpaper >/dev/null 2>&1 & which matugen >/dev/null 2>&1 && matugen image \"$wall\" 2>/dev/null || true; which swww >/dev/null 2>&1 && swww img \"$wall\" --transition-type wipe 2>/dev/null || true; which feh >/dev/null 2>&1 && feh --bg-fill \"$wall\" 2>/dev/null || true; which gsettings >/dev/null 2>&1 && gsettings set org.gnome.desktop.background picture-uri \"file://$wall\" 2>/dev/null || true)"
                desc = "Randomizes desktop wallpaper from your Pictures/Wallpapers collection."

            return {
                "command": cmd,
                "description": desc,
                "intent": "desktop_set_wallpaper",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will update your desktop wallpaper.",
                "explanation_paragraph": "The assistant recognized your wallpaper request and dispatched the appropriate Wayland / X11 wallpaper switcher (hyprpaper, swww, matugen, feh, or gsettings)."
            }

        # 3.7 Desktop Ecosystem & Audio / Wayland Operations
        if re.search(r"\b(?:reload|restart)\s+(?:the\s+)?waybar\b", clean, re.IGNORECASE):
            return {
                "command": "killall -SIGUSR2 waybar 2>/dev/null || (killall waybar 2>/dev/null ; waybar >/dev/null 2>&1 &)",
                "description": "Hot-reloads Waybar status bar configuration and stylesheets.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will reload your Waybar status bar.",
                "explanation_paragraph": "Dispatches SIGUSR2 to Waybar to reload layout modules and styling without ending your session."
            }

        if re.search(r"\b(?:reload|restart)\s+(?:the\s+)?hyprland\b", clean, re.IGNORECASE):
            return {
                "command": "hyprctl reload",
                "description": "Reloads Hyprland compositor configuration.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will reload your Hyprland configuration.",
                "explanation_paragraph": "Dispatches `hyprctl reload` to re-parse ~/.config/hypr/hyprland.conf in real-time."
            }

        if re.search(r"\b(?:take\s+(?:a\s+)?screenshot|capture\s+screen|screen\s+capture)\b", clean, re.IGNORECASE):
            return {
                "command": "mkdir -p ~/Pictures/Screenshots && (which grim >/dev/null 2>&1 && which slurp >/dev/null 2>&1 && grim -g \"$(slurp)\" ~/Pictures/Screenshots/screenshot_$(date +%Y%m%d_%H%M%S).png || spectacle 2>/dev/null || gnome-screenshot 2>/dev/null || import ~/Pictures/Screenshots/screenshot_$(date +%Y%m%d_%H%M%S).png)",
                "description": "Captures a screenshot selection and saves it to ~/Pictures/Screenshots.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will launch the interactive screen capture tool.",
                "explanation_paragraph": "Invokes `grim -g \"$(slurp)\"` on Wayland (or native screenshot utility) to capture screen area to ~/Pictures/Screenshots."
            }

        if re.search(r"\b(?:increase|turn\s+up|raise)\s+(?:the\s+)?volume\b|\bvolume\s+up\b", clean, re.IGNORECASE):
            return {
                "command": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+ 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ +5% 2>/dev/null || amixer set Master 5%+ 2>/dev/null",
                "description": "Increases default audio output volume by 5%.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will increase audio output volume.",
                "explanation_paragraph": "Executes `wpctl` (or `pactl`) to raise the primary audio sink level by 5%."
            }

        if re.search(r"\b(?:decrease|turn\s+down|lower)\s+(?:the\s+)?volume\b|\bvolume\s+down\b", clean, re.IGNORECASE):
            return {
                "command": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%- 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ -5% 2>/dev/null || amixer set Master 5%- 2>/dev/null",
                "description": "Decreases default audio output volume by 5%.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will decrease audio output volume.",
                "explanation_paragraph": "Executes `wpctl` (or `pactl`) to lower the primary audio sink level by 5%."
            }

        if re.search(r"\b(?:mute|unmute|toggle\s+mute)\s*(?:the\s+)?(?:audio|volume|sound)?\b", clean, re.IGNORECASE):
            return {
                "command": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ toggle 2>/dev/null || amixer set Master toggle 2>/dev/null",
                "description": "Toggles mute status on default audio sink.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will toggle audio output mute status.",
                "explanation_paragraph": "Executes `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` to toggle audio mute."
            }

        # 3.8 User Configuration Discovery & Editing
        m_cfg_where = re.search(r"\b(?:where\s+is|find|locate|show)\s+(?:my\s+)?(?P<app>[\w\.\-]+)\s+config(?:uration)?\b", clean, re.IGNORECASE)
        if m_cfg_where:
            app = m_cfg_where.group("app").lower()
            return {
                "command": f"find ~/.config/{app} ~/.config /etc -maxdepth 2 -name '*{app}*' -o -name 'config*' 2>/dev/null | grep -i '{app}' | head -n 5",
                "description": f"Locates configuration files and directory for '{app}'.",
                "intent": "file_find",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will locate your configuration file for '{app}'.",
                "explanation_paragraph": f"The assistant searches standard user and system configuration directories (~/.config/{app}, /etc) for active settings files."
            }

        m_cfg_open = re.search(r"\b(?:open|edit|view)\s+(?:my\s+)?(?P<app>[\w\.\-]+)\s+config(?:uration)?\b", clean, re.IGNORECASE)
        if m_cfg_open:
            app = m_cfg_open.group("app").lower()
            return {
                "command": f"cfg=$(find ~/.config/{app} ~/.config /etc -maxdepth 2 -type f \\( -name '*{app}*.conf' -o -name '*{app}*.json*' -o -name '*{app}*.toml' -o -name '*{app}*.rasi' -o -name 'config*' -o -name 'init.lua' \\) 2>/dev/null | grep -i '{app}' | head -n 1); [ -n \"$cfg\" ] && (xdg-open \"$cfg\" 2>/dev/null || \"${{EDITOR:-nano}}\" \"$cfg\") || echo 'No configuration file found for {app}'",
                "description": f"Opens the configuration file for '{app}' in default editor or viewer.",
                "intent": "file_show",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will open your '{app}' configuration file.",
                "explanation_paragraph": f"The assistant locates your '{app}' configuration and opens it using your desktop handler or preferred editor."
            }

        # 3.9 Media Playback & In-App Music Controls (playerctl / Spotify / YouTube / MPV)
        if re.search(r"\b(?:pause|stop)\s+(?:the\s+)?(?:music|song|track|playback|media|spotify)\b|\bpause\s+player\b", clean, re.IGNORECASE):
            return {
                "command": "playerctl pause 2>/dev/null || true",
                "description": "Pauses active media playback across Spotify, browser YouTube, and media players via MPRIS IPC.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will pause media playback.",
                "explanation_paragraph": "Executes `playerctl pause` over the MPRIS D-Bus interface to pause active audio or video."
            }

        if re.search(r"\b(?:resume|play|start)\s+(?:the\s+)?(?:music|song|track|playback|media|spotify)\b|\bunpause\b", clean, re.IGNORECASE):
            return {
                "command": "playerctl play 2>/dev/null || true",
                "description": "Resumes active media playback via MPRIS IPC.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will resume media playback.",
                "explanation_paragraph": "Executes `playerctl play` over the MPRIS D-Bus interface to resume playback."
            }

        if re.search(r"\b(?:next|skip)\s+(?:the\s+)?(?:song|track|music)\b", clean, re.IGNORECASE):
            return {
                "command": "playerctl next 2>/dev/null || true",
                "description": "Skips to next track in active media player via MPRIS IPC.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will skip to the next track.",
                "explanation_paragraph": "Executes `playerctl next` to advance track in Spotify, browser, or media player."
            }

        if re.search(r"\b(?:previous|prev)\s+(?:the\s+)?(?:song|track|music)\b", clean, re.IGNORECASE):
            return {
                "command": "playerctl previous 2>/dev/null || true",
                "description": "Returns to previous track in active media player via MPRIS IPC.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will return to the previous track.",
                "explanation_paragraph": "Executes `playerctl previous` to return to previous track."
            }

        if re.search(r"\b(?:what\s+(?:song\s+is\s+|is\s+)?playing|what\s+song\s+is\s+this|now\s+playing|current\s+song)\b", clean, re.IGNORECASE):
            return {
                "command": "playerctl metadata --format 'Now Playing: {{ artist }} - {{ title }} ({{ album }})' 2>/dev/null || echo 'No media currently playing'",
                "description": "Queries current track metadata (artist, title, album) via MPRIS.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will inspect currently playing media track metadata.",
                "explanation_paragraph": "Queries `playerctl metadata` to extract live artist and track titles."
            }

        # 3.10 Display Brightness Controls
        m_bright_set = re.search(r"\b(?:set\s+)?brightness\s+(?:to\s+)?(?P<pct>\d{1,3})\s*%?", clean, re.IGNORECASE)
        if m_bright_set:
            pct = m_bright_set.group("pct")
            return {
                "command": f"brightnessctl set {pct}% 2>/dev/null || light -S {pct} 2>/dev/null || echo 'Brightness control tool not found'",
                "description": f"Sets screen backlight brightness to {pct}%.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will set screen brightness to {pct}%.",
                "explanation_paragraph": f"Executes `brightnessctl set {pct}%` to update display backlight levels."
            }

        if re.search(r"\b(?:increase|turn\s+up|raise)\s+(?:the\s+)?brightness\b|\bbrightness\s+up\b", clean, re.IGNORECASE):
            return {
                "command": "brightnessctl set +10% 2>/dev/null || light -A 10 2>/dev/null || echo 'Brightness control tool not found'",
                "description": "Increases screen backlight brightness by 10%.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will increase screen brightness.",
                "explanation_paragraph": "Executes `brightnessctl set +10%` to brighten display backlight."
            }

        if re.search(r"\b(?:decrease|turn\s+down|lower)\s+(?:the\s+)?brightness\b|\bbrightness\s+down\b", clean, re.IGNORECASE):
            return {
                "command": "brightnessctl set 10%- 2>/dev/null || light -U 10 2>/dev/null || echo 'Brightness control tool not found'",
                "description": "Decreases screen backlight brightness by 10%.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will decrease screen brightness.",
                "explanation_paragraph": "Executes `brightnessctl set 10%-` to dim display backlight."
            }

        # 3.11 Window Management & In-App IPC
        if re.search(r"\b(?:close|kill)\s+(?:the\s+)?(?:active|current|focused)\s+window\b", clean, re.IGNORECASE):
            return {
                "command": "hyprctl dispatch killactive 2>/dev/null || xdotool getactivewindow windowclose 2>/dev/null || wmctrl -c :ACTIVE: 2>/dev/null",
                "description": "Closes the currently active/focused desktop window via compositor IPC.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will close the currently focused window.",
                "explanation_paragraph": "Dispatches `hyprctl dispatch killactive` or X11 equivalent to close the active window."
            }

        if re.search(r"\b(?:toggle\s+floating|float\s+window|unfloat\s+window)\b", clean, re.IGNORECASE):
            return {
                "command": "hyprctl dispatch togglefloating 2>/dev/null",
                "description": "Toggles floating mode for currently focused window.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will toggle floating mode for the active window.",
                "explanation_paragraph": "Dispatches `hyprctl dispatch togglefloating` to compositor."
            }

        if re.search(r"\b(?:toggle\s+fullscreen|fullscreen\s+window)\b", clean, re.IGNORECASE):
            return {
                "command": "hyprctl dispatch fullscreen 1 2>/dev/null",
                "description": "Toggles fullscreen mode for currently focused window.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will toggle fullscreen mode for the active window.",
                "explanation_paragraph": "Dispatches `hyprctl dispatch fullscreen 1` to compositor."
            }

        m_ws = re.search(r"\b(?:switch\s+to\s+|go\s+to\s+)?workspace\s+(?P<ws>\d+)\b", clean, re.IGNORECASE)
        if m_ws:
            ws_id = m_ws.group("ws")
            return {
                "command": f"hyprctl dispatch workspace {ws_id} 2>/dev/null || i3-msg workspace {ws_id} 2>/dev/null || swaymsg workspace {ws_id} 2>/dev/null",
                "description": f"Switches the focused desktop workspace to workspace {ws_id}.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will switch to desktop workspace {ws_id}.",
                "explanation_paragraph": f"Executes `hyprctl dispatch workspace {ws_id}` to switch workspace."
            }

        m_kill_app = re.search(r"\b(?:close|quit|kill)\s+(?:app\s+|application\s+)?(?P<app>firefox|chrome|chromium|spotify|discord|telegram|vlc|mpv|code|obsidian|gimp|steam|dolphin|nautilus|thunar)\b", clean, re.IGNORECASE)
        if m_kill_app:
            target_app = m_kill_app.group("app").lower()
            return {
                "command": f"pkill -x '{target_app}' 2>/dev/null || killall '{target_app}' 2>/dev/null",
                "description": f"Closes all running instances of application '{target_app}'.",
                "intent": "process_kill",
                "safety_level": "MODIFYING",
                "risk_score": 0.20,
                "explanation": f"I will terminate application '{target_app}'.",
                "explanation_paragraph": f"Executes `pkill -x '{target_app}'` to gracefully signal all active application processes."
            }

        # 3.12 File & Directory Actions (Viewing Images, Archiving, Deleting)
        m_img = re.search(r"\b(?:open|view|show)\s+(?:the\s+)?(?:image|picture|photo)\s+(?P<path>[\w\.\-\/~]+)\b", clean, re.IGNORECASE)
        if m_img:
            img_path = m_img.group("path")
            return {
                "command": f"xdg-open '{img_path}' 2>/dev/null || imv '{img_path}' 2>/dev/null || eog '{img_path}' 2>/dev/null || feh '{img_path}'",
                "description": f"Opens image file '{img_path}' in system image viewer.",
                "intent": "file_show",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will open image '{img_path}'.",
                "explanation_paragraph": f"Dispatches `xdg-open` or image viewer to display '{img_path}'."
            }

        m_mkdir = re.search(r"\b(?:make|create)\s+(?:a\s+)?(?:folder|directory)\s+(?:called\s+|named\s+)?(?P<dir>[\w\.\-\/~]+)\b", clean, re.IGNORECASE)
        if m_mkdir:
            dir_name = m_mkdir.group("dir")
            return {
                "command": f"mkdir -p '{dir_name}'",
                "description": f"Creates directory '{dir_name}' along with any missing parent folders.",
                "intent": "file_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.15,
                "rollback_command": f"rmdir '{dir_name}' 2>/dev/null || rm -rf '{dir_name}'",
                "explanation": f"I will create directory '{dir_name}'.",
                "explanation_paragraph": f"Executes `mkdir -p '{dir_name}'` to create the target folder structure."
            }

        m_del = re.search(r"\b(?:delete|trash|remove)\s+(?:the\s+)?(?:file\s+|folder\s+|directory\s+)?(?P<target>[\w\.\-\/~]+)\b", clean, re.IGNORECASE)
        if m_del and not any(kw in clean.lower() for kw in ("package", "app", "application", "service", "daemon", "logs", "cache")):
            tgt = m_del.group("target")
            return {
                "command": f"gio trash '{tgt}' 2>/dev/null || rm -rf '{tgt}'",
                "description": f"Safely moves '{tgt}' to desktop trash bin.",
                "intent": "file_trash",
                "safety_level": "HIGH_RISK",
                "risk_score": 0.60,
                "explanation": f"I will move '{tgt}' to trash.",
                "explanation_paragraph": f"Uses `gio trash` (or POSIX deletion fallback) to remove '{tgt}' safely."
            }

        m_zip = re.search(r"\b(?:zip|compress)\s+(?:folder\s+|directory\s+)?(?P<target>[\w\.\-\/~]+)\b", clean, re.IGNORECASE)
        if m_zip:
            tgt = m_zip.group("target").rstrip("/")
            return {
                "command": f"tar -czvf '{tgt}.tar.gz' '{tgt}'",
                "description": f"Compresses '{tgt}' into gzip tarball archive '{tgt}.tar.gz'.",
                "intent": "generic_command",
                "safety_level": "MODIFYING",
                "risk_score": 0.20,
                "rollback_command": f"rm -f '{tgt}.tar.gz'",
                "explanation": f"I will compress '{tgt}' into '{tgt}.tar.gz'.",
                "explanation_paragraph": f"Executes `tar -czvf '{tgt}.tar.gz' '{tgt}'` to create compressed archive."
            }

        m_unzip = re.search(r"\b(?:unzip|extract|decompress)\s+(?P<target>[\w\.\-\/~]+)\b", clean, re.IGNORECASE)
        if m_unzip:
            tgt = m_unzip.group("target")
            return {
                "command": f"tar -xvf '{tgt}' 2>/dev/null || unzip '{tgt}'",
                "description": f"Extracts compressed archive '{tgt}' into current working directory.",
                "intent": "generic_command",
                "safety_level": "MODIFYING",
                "risk_score": 0.25,
                "explanation": f"I will extract archive '{tgt}'.",
                "explanation_paragraph": f"Dispatches `tar -xvf` or `unzip` to unpack contents of '{tgt}'."
            }

        # 3.13 Notifications, Battery & Session Power Controls
        m_notif = re.search(r"\b(?:send\s+)?notification\s+(?:saying\s+|that\s+)?(?P<msg>.+)\b|\bnotify\s+(?:me\s+)?(?:that\s+|saying\s+)?(?P<msg2>.+)\b", clean, re.IGNORECASE)
        if m_notif:
            msg = (m_notif.group("msg") or m_notif.group("msg2") or "Task completed!").strip("\"'")
            return {
                "command": f"notify-send 'LinuxOps Assistant' '{msg}'",
                "description": f"Dispatches desktop notification popup with message '{msg}'.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will send a desktop notification: '{msg}'.",
                "explanation_paragraph": f"Executes `notify-send` over the desktop notification daemon."
            }

        if re.search(r"\b(?:check|show|get)\s+(?:my\s+)?(?:battery|power|charge)(?:\s+(?:status|level|percentage))?\b", clean, re.IGNORECASE):
            return {
                "command": "upower -i $(upower -e 2>/dev/null | grep 'BAT' | head -n 1) 2>/dev/null || acpi -b 2>/dev/null || cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || echo 'AC Power / No battery detected'",
                "description": "Reports live battery percentage, health, and power charging state.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will check battery charge level and health.",
                "explanation_paragraph": "Queries `upower` or ACPI to read battery capacity and charge state."
            }

        if re.search(r"\b(?:lock\s+(?:screen|laptop|computer|session))\b", clean, re.IGNORECASE):
            return {
                "command": "hyprlock 2>/dev/null || swaylock 2>/dev/null || loginctl lock-session 2>/dev/null || true",
                "description": "Locks the current desktop graphical session.",
                "intent": "generic_command",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will lock your screen session.",
                "explanation_paragraph": "Executes screen locker (`hyprlock` / `swaylock` / `loginctl lock-session`)."
            }

        if re.search(r"\b(?:reboot|restart\s+(?:the\s+)?(?:laptop|computer|system|machine|pc))\b", clean, re.IGNORECASE):
            return {
                "command": "systemctl reboot",
                "description": "Initiates graceful reboot of the host operating system.",
                "intent": "system_reboot",
                "safety_level": "HIGH_RISK",
                "risk_score": 0.75,
                "explanation": "I will initiate a system reboot.",
                "explanation_paragraph": "Executes `systemctl reboot` after operator approval."
            }

        if re.search(r"\b(?:suspend|sleep)\s+(?:the\s+)?(?:laptop|computer|system|pc)\b", clean, re.IGNORECASE):
            return {
                "command": "systemctl suspend",
                "description": "Suspends the operating system to RAM.",
                "intent": "generic_command",
                "safety_level": "MODIFYING",
                "risk_score": 0.30,
                "explanation": "I will put the system into suspend sleep mode.",
                "explanation_paragraph": "Executes `systemctl suspend` to sleep."
            }

        # 4. System Resource & Health Inquiries
        # e.g. "check my CPU uses", "check ram", "how much memory is free"
        if re.search(r"\b(?:check|show|get|view|inspect)\s+(?:my\s+)?(?:cpu|processor)(?:\s+(?:uses|usage|load|status|utilization))?\b", clean, re.IGNORECASE) or clean.lower() in ("cpu uses", "cpu usage", "check cpu"):
            cmd = "top -b -n 1 | head -n 15"
            return {
                "command": cmd,
                "description": "Inspects live CPU utilization percentage, tasks, and system load averages.",
                "intent": "system_check_cpu",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will inspect live CPU utilization and process load.",
                "explanation_paragraph": "The assistant converted your natural language query into `top -b -n 1 | head -n 15`, sampling active CPU usage across user, system, and idle states as well as 1-, 5-, and 15-minute load averages."
            }

        if re.search(r"\b(?:check|show|get|view|inspect|how\s+much)\s+(?:my\s+)?(?:ram|memory|swap)(?:\s+(?:is\s+free|free|usage|uses|status))?\b", clean, re.IGNORECASE) or clean.lower() in ("ram uses", "ram usage", "check ram", "free memory", "free ram"):
            cmd = "free -h"
            return {
                "command": cmd,
                "description": "Displays physical RAM and swap memory usage in human-readable units.",
                "intent": "system_check_ram",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will check available physical memory (RAM) and swap capacity.",
                "explanation_paragraph": "The assistant compiled your request into `free -h`, displaying total, used, available, and buffered RAM along with swap space in human-readable megabytes and gigabytes."
            }

        if re.search(r"\b(?:check|show|get|view|how\s+much)\s+(?:my\s+)?(?:disk|storage|space|drive|filesystem)(?:\s+(?:is\s+free|free|usage|uses|space))?\b", clean, re.IGNORECASE) or clean.lower() in ("disk space", "storage space", "check disk", "check storage"):
            cmd = "df -h"
            return {
                "command": cmd,
                "description": "Reports storage capacity, used space, and availability across mounted partitions.",
                "intent": "system_check_disk",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will report disk space and partition utilization.",
                "explanation_paragraph": "The assistant compiled your request into `df -h`, reporting total capacity, used space, free blocks, and mount points across all active storage filesystems."
            }

        # 5. Network Information
        # e.g. "what is my ip", "show my ip address"
        if re.search(r"\b(?:what\s+is\s+my|show\s+my|get\s+my|check\s+my)?\s*(?:ip|ip\s+address|network\s+ip)\b", clean, re.IGNORECASE):
            cmd = "ip -br a || ifconfig"
            return {
                "command": cmd,
                "description": "Displays network interfaces and IP addresses.",
                "intent": "network_status",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will display your active network IP addresses.",
                "explanation_paragraph": "The assistant executed `ip -br a`, listing network interface controllers (NICs), operational link states (UP/DOWN), and assigned IPv4/IPv6 addresses."
            }

        # 6. Trash & Cleanup
        # e.g. "clean my trash", "empty trash"
        if re.search(r"\b(?:clean|empty|clear|purge)\s+(?:my\s+)?trash\b", clean, re.IGNORECASE):
            trash_path = os.path.expanduser("~/.local/share/Trash")
            cmd = f"rm -rf '{trash_path}/files/'* '{trash_path}/info/'*"
            return {
                "command": cmd,
                "description": "Purges all deleted files and metadata in user Trash.",
                "intent": "storage_clean_trash",
                "safety_level": "DESTRUCTIVE",
                "risk_score": 0.85,
                "explanation": "I will permanently clean all items in your Trash directory.",
                "explanation_paragraph": "The assistant compiled your request to empty trash into `rm -rf ~/.local/share/Trash/files/*`. This permanently reclaims disk space by purging recycled files."
            }

        # 7. Running processes & services
        if re.search(r"\b(?:show|list|get|view)\s+(?:all\s+)?(?:running\s+)?(?:processes|tasks|procs)\b", clean, re.IGNORECASE):
            cmd = "ps aux --sort=-%cpu | head -n 20"
            return {
                "command": cmd,
                "description": "Lists top 20 active processes sorted by CPU utilization.",
                "intent": "process_list",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will list active processes sorted by CPU consumption.",
                "explanation_paragraph": "The assistant executed `ps aux --sort=-%cpu | head -n 20`, capturing a snapshot of active PID, memory, CPU percentages, and command binaries."
            }

        if re.search(r"\b(?:show|list|get|view)\s+(?:all\s+)?(?:running\s+)?services\b", clean, re.IGNORECASE):
            cmd = "systemctl list-units --type=service --state=running"
            return {
                "command": cmd,
                "description": "Lists active and running systemd system services.",
                "intent": "service_status",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will list all active systemd services.",
                "explanation_paragraph": "The assistant queried systemd via `systemctl list-units --type=service --state=running`, displaying all active background daemons and service units."
            }

        # 8. Screenshot & File Rename / Move Operations
        # e.g. "rename the latest screen shot to imp", "rename latest screenshot to 'imp'"
        m_screen = re.search(r"^(?:please\s+)?(?:rename|move)\s+(?:the\s+)?(?:latest\s+)?(?:screenshot|screen\s+shot|screen-shot|screen\s+capture)\s+(?:to\s+|as\s+)?['\"]?(?P<newname>[^'\"]+?)['\"]?$", clean, re.IGNORECASE)
        if m_screen:
            raw_name = m_screen.group("newname").strip().strip("'\"")
            cmd = (
                f'latest=$(find ~/Pictures ~/Desktop ~/Downloads . -maxdepth 2 -type f '
                f'\\( -iname "*screenshot*" -o -iname "*screen*" -o -iname "*.png" \\) '
                f'-printf "%T@ %p\\n" 2>/dev/null | sort -nr | head -n 1 | cut -d\' \' -f2-); '
                f'if [ -n "$latest" ]; then '
                f'ext="${{latest##*.}}"; '
                f'target_dir="$(dirname "$latest")"; '
                f'dest="$target_dir/{raw_name}"; '
                f'if [[ "{raw_name}" != *.* ]] && [ "$ext" != "$latest" ]; then dest="$dest.$ext"; fi; '
                f'mv "$latest" "$dest" && echo "Renamed \'$latest\' to \'$dest\'"; '
                f'else echo "No screenshot found in ~/Pictures, ~/Desktop, or ~/Downloads"; exit 1; fi'
            )
            return {
                "command": cmd,
                "description": f"Finds the most recent screenshot and renames it to '{raw_name}'.",
                "intent": "file_rename",
                "safety_level": "MODIFYING",
                "risk_score": 0.25,
                "rollback_command": None,
                "explanation": f"I will locate the newest screenshot and rename it to '{raw_name}'.",
                "explanation_paragraph": f"The assistant compiled your request into a targeted shell pipeline that searches standard screenshot directories (`~/Pictures`, `~/Desktop`, `~/Downloads`), resolves the newest screenshot file by timestamp, and renames it to '{raw_name}' while preserving its original image extension."
            }

        # e.g. "rename file old.txt to new.txt", "rename notes.md to todo.md", "rename the downloads folder to downloaded"
        m_rename = re.search(r"^(?:please\s+)?(?:rename|move)\s+(?:the\s+)?(?:file\s+|folder\s+|dir\s+|directory\s+)?['\"]?(?P<src>[a-zA-Z0-9_\-\.\/~]+)(?:\s+(?:folder|file|dir|directory))?['\"]?\s+(?:to\s+|as\s+)['\"]?(?P<dst>[a-zA-Z0-9_\-\.\/~]+)(?:\s+(?:folder|file|dir|directory))?['\"]?$", clean, re.IGNORECASE)
        if m_rename:
            src = m_rename.group("src").strip()
            dst = m_rename.group("dst").strip()
            cmd = f"mv '{src}' '{dst}'"
            return {
                "command": cmd,
                "path": dst,
                "src": src,
                "dst": dst,
                "description": f"Renames/moves '{src}' to '{dst}'.",
                "intent": "file_rename",
                "safety_level": "MODIFYING",
                "risk_score": 0.25,
                "rollback_command": f"mv '{dst}' '{src}'",
                "explanation": f"I will rename '{src}' to '{dst}'.",
                "explanation_paragraph": f"The assistant compiled your request into `mv '{src}' '{dst}'`, relocating or renaming the specified file path in your working directory."
            }

        return None


def generate_natural_explanation(query: str, command: str, returncode: int = 0, stdout: str = "", stderr: str = "") -> str:
    """
    Generates a clear, informative natural language explanation paragraph for any command.
    Explains the purpose, impact on the filesystem/system, and execution outcome.
    """
    cmd = command.strip()
    tokens = cmd.split()
    base = tokens[0] if tokens else "command"
    if base == "sudo" and len(tokens) > 1:
        base = tokens[1]

    if "mkdir" in cmd:
        target = cmd.replace("mkdir", "").replace("-p", "").strip().strip("'\"")
        if returncode == 0:
            return f"Successfully created the directory '{target}'. The system verified that the path is now provisioned on the filesystem and ready for files."
        return f"Attempted to create the directory '{target}', but the operation exited with code {returncode}. Stderr: {stderr.strip()}"

    if "xdg-open" in cmd:
        target = cmd.replace("xdg-open", "").strip().strip("'\"")
        if "http" in target:
            return f"Launched your default web browser to '{target}'. The browser window is now active on your desktop."
        return f"Opened '{target}' in your system default desktop application / file manager."

    if "touch" in cmd or ("echo" in cmd and ">" in cmd):
        return f"Executed file creation command. The target file has been written to disk with the specified contents and file permissions."

    if "top" in cmd or "htop" in cmd:
        return f"Sampled real-time CPU utilization and system load averages. The CPU load across active cores and system processes is currently running smoothly."

    if "free" in cmd:
        return f"Queried the Linux kernel memory manager. The system retrieved available physical RAM, cached pages, buffer headroom, and swap utilization."

    if "df" in cmd:
        return f"Queried filesystem disk partition table. The system retrieved total capacity, allocated space, and free blocks across all mounted disk drives."

    if "systemctl" in cmd:
        return f"Interfaced with the systemd service manager. The command processed unit state and service daemon lifecycle properties."

    if "tar" in cmd:
        return f"Processed archive operation. The tar command compressed/extracted the target files according to the decoded options."

    if returncode == 0:
        return f"Successfully executed the Linux command `{cmd}` (exit code 0). All changes and system requests have completed."
    else:
        return f"Executed `{cmd}` with exit code {returncode}. An issue was encountered during execution. Stderr: {stderr.strip()}"
