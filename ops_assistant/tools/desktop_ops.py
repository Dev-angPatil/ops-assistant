"""
Desktop & OS Operations — freedesktop.org compliant GUI integration
for opening folders, launching files, viewing images, opening browsers,
and safe file moving/copying/trashing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


import re


def _expand_path(raw_path: str) -> Path:
    """Expand ~ and environment variables, resolve path."""
    return Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def find_target_folder(target: str, max_depth: int = 5) -> Optional[Path]:
    """
    Intelligently search the filesystem (cwd, ~, Projects, Documents, Desktop, etc.)
    for a matching directory name.
    """
    clean = target.strip().strip("'\"").strip()
    if not clean:
        return None

    # Strip conversational prefixes
    clean_name = re.sub(r"^(?:my\s+|the\s+)", "", clean, flags=re.IGNORECASE)
    clean_name = re.sub(r"^(?:folder\s+|dir\s+|directory\s+)", "", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s+(?:folder|dir|directory)$", "", clean_name, flags=re.IGNORECASE).strip()

    # 1. Check direct path if path-like
    try:
        p = _expand_path(clean)
        if p.is_dir():
            return p
        p_clean = _expand_path(clean_name)
        if p_clean.is_dir():
            return p_clean
    except Exception:
        pass

    target_lower = clean_name.lower()
    home = Path.home()
    cwd = Path.cwd()

    priority_roots = [
        cwd,
        home / "Projects",
        home / "Documents",
        home / "Desktop",
        home / "Downloads",
        home / "code",
        home / "workspace",
        home / "dev",
        home / "src",
        home
    ]

    visited = set()
    ignored_dir_names = {
        "node_modules", ".git", ".cache", ".local", ".cargo", ".rustup",
        ".venv", "venv", ".env", "env", "__pycache__", "dist", "build", "target"
    }

    # Pass 1: exact case-insensitive match
    for root in priority_roots:
        if not root.exists() or str(root) in visited:
            continue
        visited.add(str(root))
        try:
            for dirpath, dirnames, _ in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ignored_dir_names]
                try:
                    rel = Path(dirpath).relative_to(root)
                    if len(rel.parts) > max_depth:
                        dirnames.clear()
                        continue
                except Exception:
                    pass

                for d in dirnames:
                    if d.lower() == target_lower:
                        return Path(dirpath) / d
        except Exception:
            pass

    # Pass 2: substring match (e.g. "dsa" in "DSA-Leetcode" or "my_dsa")
    visited.clear()
    for root in priority_roots:
        if not root.exists() or str(root) in visited:
            continue
        visited.add(str(root))
        try:
            for dirpath, dirnames, _ in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ignored_dir_names]
                try:
                    rel = Path(dirpath).relative_to(root)
                    if len(rel.parts) > max_depth:
                        dirnames.clear()
                        continue
                except Exception:
                    pass

                for d in dirnames:
                    if target_lower in d.lower():
                        return Path(dirpath) / d
        except Exception:
            pass

    return None


def find_target_file(target: str, max_depth: int = 5) -> Optional[Path]:
    """
    Intelligently search the filesystem for a matching file name.
    """
    clean = target.strip().strip("'\"").strip()
    if not clean:
        return None

    try:
        p = _expand_path(clean)
        if p.is_file():
            return p
    except Exception:
        pass

    target_lower = clean.lower()
    home = Path.home()
    cwd = Path.cwd()

    priority_roots = [
        cwd,
        home / "Projects",
        home / "Documents",
        home / "Desktop",
        home / "Downloads",
        home / "code",
        home / "workspace",
        home
    ]

    visited = set()
    ignored_dir_names = {
        "node_modules", ".git", ".cache", ".local", ".cargo", ".rustup",
        ".venv", "venv", ".env", "env", "__pycache__", "dist", "build", "target"
    }

    for root in priority_roots:
        if not root.exists() or str(root) in visited:
            continue
        visited.add(str(root))
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ignored_dir_names]
                try:
                    rel = Path(dirpath).relative_to(root)
                    if len(rel.parts) > max_depth:
                        dirnames.clear()
                        continue
                except Exception:
                    pass

                for f in filenames:
                    if f.lower() == target_lower or target_lower in f.lower():
                        return Path(dirpath) / f
        except Exception:
            pass

    return None


def open_folder(path: str = "~", create_if_missing: bool = False) -> Dict[str, Any]:
    """
    Open a directory in the default system file manager. If path does not exist directly,
    scans filesystem for matching folder name.
    """
    p = _expand_path(path)
    if not p.exists() or not p.is_dir():
        discovered = find_target_folder(path)
        if discovered and discovered.is_dir():
            p = discovered
        elif create_if_missing:
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                p = Path.home()
        else:
            return {
                "success": False,
                "path": str(p),
                "error": f"Directory '{path}' not found across your computer (scanned home, projects, documents, desktop).",
                "action": "open_folder"
            }
    elif not p.is_dir():
        p = p.parent

    # Try xdg-open first, fallback to known Linux file managers
    try:
        proc = subprocess.Popen(
            ["xdg-open", str(p)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return {
            "success": True,
            "path": str(p),
            "pid": proc.pid,
            "message": f"Opened directory in file manager: {p}",
            "action": "open_folder"
        }
    except FileNotFoundError:
        # Fallbacks
        for fm in ("nautilus", "dolphin", "thunar", "pcmanfm", "caja", "nemo"):
            if shutil.which(fm):
                proc = subprocess.Popen(
                    [fm, str(p)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return {
                    "success": True,
                    "path": str(p),
                    "pid": proc.pid,
                    "file_manager": fm,
                    "message": f"Opened directory in {fm}: {p}",
                    "action": "open_folder"
                }
        return {
            "success": False,
            "path": str(p),
            "error": "No supported desktop file manager (xdg-open/nautilus/dolphin/thunar) found.",
            "action": "open_folder"
        }
    except Exception as e:
        return {
            "success": False,
            "path": str(p),
            "error": str(e),
            "action": "open_folder"
        }


def open_file(path: str) -> Dict[str, Any]:
    """
    Open a file using the system default application or editor.
    """
    p = _expand_path(path)
    if not p.exists() or not p.is_file():
        discovered = find_target_file(path)
        if discovered and discovered.is_file():
            p = discovered
        else:
            return {
                "success": False,
                "path": str(p),
                "error": f"File '{path}' not found across your computer (scanned home, projects, documents, desktop).",
                "action": "open_file"
            }

    try:
        proc = subprocess.Popen(
            ["xdg-open", str(p)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return {
            "success": True,
            "path": str(p),
            "pid": proc.pid,
            "message": f"Opened file in default application: {p}",
            "action": "open_file"
        }
    except FileNotFoundError:
        editor = os.environ.get("EDITOR", "nano")
        return {
            "success": False,
            "path": str(p),
            "error": f"xdg-open not available. You can view it with: {editor} {p}",
            "action": "open_file"
        }
    except Exception as e:
        return {
            "success": False,
            "path": str(p),
            "error": str(e),
            "action": "open_file"
        }


def open_image(path: str) -> Dict[str, Any]:
    """
    Open an image using the default desktop image viewer (eog, feh, xdg-open).
    """
    p = _expand_path(path)
    if not p.exists():
        return {
            "success": False,
            "path": str(p),
            "error": f"Image file does not exist: {p}",
            "action": "open_image"
        }

    try:
        viewers = ["xdg-open", "eog", "feh", "gwenview", "display", "shotwell"]
        for v in viewers:
            if shutil.which(v):
                proc = subprocess.Popen(
                    [v, str(p)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return {
                    "success": True,
                    "path": str(p),
                    "viewer": v,
                    "pid": proc.pid,
                    "message": f"Opened image with {v}: {p}",
                    "action": "open_image"
                }
        return {
            "success": False,
            "path": str(p),
            "error": "No image viewer or xdg-open found.",
            "action": "open_image"
        }
    except Exception as e:
        return {
            "success": False,
            "path": str(p),
            "error": str(e),
            "action": "open_image"
        }


def open_browser(url: str = "https://google.com") -> Dict[str, Any]:
    """
    Open a web URL in the user default web browser.
    """
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://", "file://", "about:")):
        clean_url = "https://" + clean_url

    try:
        opened = webbrowser.open(clean_url, new=2)
        if opened:
            return {
                "success": True,
                "url": clean_url,
                "message": f"Opened browser to: {clean_url}",
                "action": "open_browser"
            }
        else:
            proc = subprocess.Popen(
                ["xdg-open", clean_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return {
                "success": True,
                "url": clean_url,
                "pid": proc.pid,
                "message": f"Launched browser with xdg-open: {clean_url}",
                "action": "open_browser"
            }
    except Exception as e:
        return {
            "success": False,
            "url": clean_url,
            "error": str(e),
            "action": "open_browser"
        }


def move_path(src: str, dst: str) -> Dict[str, Any]:
    """
    Move a file or directory with existence checking and rollback tracking.
    """
    s = _expand_path(src)
    d = _expand_path(dst)

    if not s.exists():
        return {
            "success": False,
            "src": str(s),
            "dst": str(d),
            "error": f"Source path does not exist: {s}",
            "action": "move_path"
        }

    if d.is_dir():
        final_dst = d / s.name
    else:
        final_dst = d
        final_dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(s), str(final_dst))
        return {
            "success": True,
            "src": str(s),
            "dst": str(final_dst),
            "message": f"Moved {s} -> {final_dst}",
            "rollback_command": f"mv '{final_dst}' '{s}'",
            "action": "move_path"
        }
    except Exception as e:
        return {
            "success": False,
            "src": str(s),
            "dst": str(final_dst),
            "error": str(e),
            "action": "move_path"
        }


def copy_path(src: str, dst: str) -> Dict[str, Any]:
    """
    Copy a file or directory recursively.
    """
    s = _expand_path(src)
    d = _expand_path(dst)

    if not s.exists():
        return {
            "success": False,
            "src": str(s),
            "dst": str(d),
            "error": f"Source path does not exist: {s}",
            "action": "copy_path"
        }

    try:
        if s.is_dir():
            if d.exists() and d.is_dir():
                target = d / s.name
            else:
                target = d
            shutil.copytree(str(s), str(target), dirs_exist_ok=True)
        else:
            if d.is_dir():
                target = d / s.name
            else:
                target = d
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(s), str(target))

        return {
            "success": True,
            "src": str(s),
            "dst": str(target),
            "message": f"Copied {s} -> {target}",
            "rollback_command": f"rm -rf '{target}'",
            "action": "copy_path"
        }
    except Exception as e:
        return {
            "success": False,
            "src": str(s),
            "dst": str(d),
            "error": str(e),
            "action": "copy_path"
        }


def trash_path(path: str) -> Dict[str, Any]:
    """
    Safely move a file/directory to the user trash directory (~/.local/share/Trash/files)
    instead of permanently deleting it.
    """
    p = _expand_path(path)
    if not p.exists():
        return {
            "success": False,
            "path": str(p),
            "error": f"Path does not exist: {p}",
            "action": "trash_path"
        }

    trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
    trash_dir.mkdir(parents=True, exist_ok=True)

    dest = trash_dir / p.name
    counter = 1
    stem = p.stem
    suffix = p.suffix
    while dest.exists():
        dest = trash_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        shutil.move(str(p), str(dest))
        return {
            "success": True,
            "original_path": str(p),
            "trash_path": str(dest),
            "message": f"Safely trashed {p} -> {dest}",
            "rollback_command": f"mv '{dest}' '{p}'",
            "action": "trash_path"
        }
    except Exception as e:
        return {
            "success": False,
            "path": str(p),
            "error": str(e),
            "action": "trash_path"
        }


def find_available_wallpapers() -> List[str]:
    """
    Scans common user and system wallpaper directories to locate available background images.
    """
    candidate_dirs = [
        Path.home() / "Pictures" / "Photos" / "Wallpaper",
        Path.home() / "Pictures" / "Wallpapers",
        Path.home() / "Pictures" / "Photos",
        Path.home() / "Pictures" / "Assets & Stock",
        Path.home() / "Pictures",
        Path.home() / ".config" / "hypr" / "themes",
        Path("/usr/share/backgrounds"),
        Path("/usr/share/wallpapers"),
    ]
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp"}
    found: List[str] = []

    for d in candidate_dirs:
        if d.is_dir():
            try:
                for f in d.rglob("*"):
                    if f.is_file() and f.suffix.lower() in extensions:
                        found.append(str(f))
                        if len(found) >= 50:
                            break
            except Exception:
                continue

    return found


def set_wallpaper(image_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Changes the desktop wallpaper across Hyprland (hyprpaper/swww), GNOME (gsettings),
    KDE (plasma-apply-wallpaperimage), Waypaper, or X11 (feh/nitrogen).
    """
    import random

    if image_path:
        target = _expand_path(image_path)
        if not target.exists() or not target.is_file():
            return {
                "success": False,
                "error": f"Wallpaper file does not exist: {target}",
                "action": "set_wallpaper"
            }
        chosen_path = str(target)
    else:
        avail = find_available_wallpapers()
        if not avail:
            return {
                "success": False,
                "error": "No wallpaper images found in ~/Pictures/Wallpapers or system directories.",
                "action": "set_wallpaper"
            }
        chosen_path = random.choice(avail)

    executed_cmd = ""
    # 1. Hyprland / Wayland with hyprpaper
    if shutil.which("hyprpaper"):
        try:
            cfg_dir = Path.home() / ".config" / "hypr"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "hyprpaper.conf"
            cfg_file.write_text(f"preload = {chosen_path}\nwallpaper = ,{chosen_path}\nsplash = false\n", encoding="utf-8")
            subprocess.run(["pkill", "-x", "hyprpaper"], capture_output=True, timeout=1)
            subprocess.Popen(["hyprpaper"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            executed_cmd = f"hyprpaper (set wallpaper: {chosen_path})"
        except Exception:
            pass

    # 2. matugen on HyDE / Material You
    if shutil.which("matugen"):
        try:
            subprocess.run(["matugen", "image", chosen_path], capture_output=True, timeout=2)
        except Exception:
            pass

    # 3. swww on Wayland
    if not executed_cmd and shutil.which("swww"):
        try:
            subprocess.run(["swww", "img", chosen_path, "--transition-type", "wipe"], capture_output=True, timeout=2)
            executed_cmd = f"swww img '{chosen_path}' --transition-type wipe"
        except Exception:
            pass

    # 4. GNOME gsettings
    if not executed_cmd and shutil.which("gsettings"):
        try:
            file_uri = f"file://{chosen_path}"
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri], capture_output=True, timeout=2)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri], capture_output=True, timeout=2)
            executed_cmd = f"gsettings set org.gnome.desktop.background picture-uri 'file://{chosen_path}'"
        except Exception:
            pass

    # 5. KDE Plasma
    if not executed_cmd and shutil.which("plasma-apply-wallpaperimage"):
        try:
            subprocess.run(["plasma-apply-wallpaperimage", chosen_path], capture_output=True, timeout=2)
            executed_cmd = f"plasma-apply-wallpaperimage '{chosen_path}'"
        except Exception:
            pass

    # 6. feh on X11
    if not executed_cmd and shutil.which("feh"):
        try:
            subprocess.run(["feh", "--bg-fill", chosen_path], capture_output=True, timeout=2)
            executed_cmd = f"feh --bg-fill '{chosen_path}'"
        except Exception:
            pass

    if not executed_cmd:
        # Fallback: launch image in default viewer or waypaper
        if shutil.which("waypaper"):
            subprocess.Popen(["waypaper", "--wallpaper", chosen_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            executed_cmd = f"waypaper --wallpaper '{chosen_path}'"
        else:
            return {
                "success": True,
                "wallpaper": chosen_path,
                "command": f"xdg-open '{chosen_path}'",
                "message": f"Selected wallpaper '{chosen_path}'. (Install hyprpaper, swww, or feh for background daemons)",
                "action": "set_wallpaper"
            }

    return {
        "success": True,
        "wallpaper": chosen_path,
        "command": executed_cmd,
        "message": f"Changed desktop wallpaper to: {chosen_path}",
        "action": "set_wallpaper"
    }
