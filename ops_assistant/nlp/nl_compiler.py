"""
Natural Language Command Compiler — Translates arbitrary English sentences,
voice transcriptions, and complex instructions into valid Linux shell commands
with zero external runtime dependencies.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import urllib.parse
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
        "gitlab": "https://gitlab.com",
        "bitbucket": "https://bitbucket.org",
        "google": "https://google.com",
        "chatgpt": "https://chatgpt.com",
        "chat gpt": "https://chatgpt.com",
        "openai": "https://chatgpt.com",
        "claude": "https://claude.ai",
        "anthropic": "https://claude.ai",
        "huggingface": "https://huggingface.co",
        "hugging face": "https://huggingface.co",
        "kaggle": "https://kaggle.com",
        "colab": "https://colab.research.google.com",
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
        "discord": "https://discord.com/app",
        "notion": "https://notion.so",
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
        "settings": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
        "text editor": ["gedit", "kate", "mousepad", "nano", "xed"],
    }

    STANDARD_FOLDERS = {
        "downloads": "~/Downloads",
        "download": "~/Downloads",
        "downlaods": "~/Downloads",
        "downlaod": "~/Downloads",
        "downlod": "~/Downloads",
        "downlods": "~/Downloads",
        "dwnload": "~/Downloads",
        "dwnloads": "~/Downloads",
        "documents": "~/Documents",
        "document": "~/Documents",
        "documnts": "~/Documents",
        "documnt": "~/Documents",
        "docs": "~/Documents",
        "doc": "~/Documents",
        "desktop": "~/Desktop",
        "desktops": "~/Desktop",
        "pictures": "~/Pictures",
        "picture": "~/Pictures",
        "picturs": "~/Pictures",
        "pictur": "~/Pictures",
        "photos": "~/Pictures",
        "photo": "~/Pictures",
        "pics": "~/Pictures",
        "pic": "~/Pictures",
        "images": "~/Pictures",
        "image": "~/Pictures",
        "music": "~/Music",
        "videos": "~/Videos",
        "video": "~/Videos",
        "movies": "~/Videos",
        "movie": "~/Videos",
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

        # Clean punctuation and apply phonetic/Hinglish normalizations
        from ops_assistant.voice.transcriber import PhoneticNormalizer
        clean = re.sub(r"^\$\s*", "", raw)
        clean = re.sub(r"[\.!\?]+$", "", clean).strip()
        clean = PhoneticNormalizer.normalize(clean)

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

        # e.g. "create file notes.txt with content 'hello'", "write 'hello' to notes.txt"
        m = re.search(r"^(?:create|make|touch)\s+(?:a\s+|one\s+|new\s+)?file\s+(?P<file>[a-zA-Z0-9_\-\.\/~]+)(?:\s+with\s+(?:content|text)\s+['\"]?(?P<content>.*?)['\"]?)?$", clean, re.IGNORECASE)
        if m:
            filename = m.group("file").strip()
            content = (m.group("content") or "").strip()
            if content:
                cmd = f"echo '{content}' > '{filename}'"
                desc = f"Creates file '{filename}' with content."
            else:
                cmd = f"touch '{filename}'"
                desc = f"Creates empty file '{filename}'."
            return {
                "command": cmd,
                "path": filename,
                "content": content,
                "description": desc,
                "intent": "file_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.20,
                "rollback_command": f"rm -f '{filename}'",
                "explanation": f"I will create the file '{filename}'.",
                "explanation_paragraph": f"The assistant compiled your request to create the file `{filename}`."
            }

        # ---------------------------------------------------------------------
        # 3. File Permissions & Ownership
        # ---------------------------------------------------------------------
        # e.g. "make script.sh executable", "give execute permission to script.sh", "make build.sh runnable"
        m = re.search(r"^(?:please\s+)?(?:make|give|set)\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?\s+(?:as\s+)?(?:executable|runnable|exec\s+permission|execute\s+permission)\b", clean, re.IGNORECASE)
        if not m:
            m = re.search(r"^(?:please\s+)?(?:give|add|set)\s+(?:execute|executable|exec)\s+permission\s+(?:to|for|on)\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if not m:
            m = re.search(r"^chmod\s+\+x\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            target = m.group("target").strip()
            cmd = f"chmod +x '{target}'"
            return {
                "command": cmd,
                "path": target,
                "description": f"Grants execution permissions to '{target}'.",
                "intent": "perm_change",
                "safety_level": "MODIFYING",
                "risk_score": 0.20,
                "rollback_command": f"chmod -x '{target}'",
                "explanation": f"I will make '{target}' executable (chmod +x).",
                "explanation_paragraph": f"The assistant compiled your permission instruction into `chmod +x '{target}'`, allowing the file to be directly executed as a script or program."
            }

        # e.g. "change permission of file.txt to 755", "chmod 644 file.txt"
        m = re.search(r"^(?:change|set)\s+(?:file\s+)?permission(?:s)?\s+(?:of|for|on)\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?\s+(?:to\s+)?(?P<mode>[0-7]{3,4})$", clean, re.IGNORECASE)
        if not m:
            m = re.search(r"^chmod\s+(?P<mode>[0-7]{3,4})\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            target = m.group("target").strip()
            mode = m.group("mode").strip()
            cmd = f"chmod {mode} '{target}'"
            return {
                "command": cmd,
                "path": target,
                "description": f"Changes permissions of '{target}' to {mode}.",
                "intent": "perm_change",
                "safety_level": "MODIFYING",
                "risk_score": 0.25,
                "rollback_command": None,
                "explanation": f"I will set permissions of '{target}' to {mode}.",
                "explanation_paragraph": f"The assistant executed `chmod {mode} '{target}'` to adjust filesystem read, write, and execute bits."
            }

        # e.g. "change owner of file.txt to god", "chown user:group file.txt"
        m = re.search(r"^(?:change|set)\s+(?:owner|ownership)\s+(?:of|for|on)\s+['\"]?(?P<target>[a-zA-Z0-9_\-\.\/~]+)['\"]?\s+(?:to\s+)?(?P<owner>[a-zA-Z0-9_\-]+(?::[a-zA-Z0-9_\-]+)?)$", clean, re.IGNORECASE)
        if m:
            target = m.group("target").strip()
            owner = m.group("owner").strip()
            cmd = f"sudo chown '{owner}' '{target}'"
            return {
                "command": cmd,
                "path": target,
                "description": f"Changes ownership of '{target}' to '{owner}'.",
                "intent": "perm_change",
                "safety_level": "MODIFYING",
                "risk_score": 0.35,
                "rollback_command": None,
                "explanation": f"I will change the owner of '{target}' to '{owner}'.",
                "explanation_paragraph": f"The assistant compiled your request into `sudo chown '{owner}' '{target}'`."
            }

        # ---------------------------------------------------------------------
        # 4. Compression & Archives (tar, zip, untar, unzip)
        # ---------------------------------------------------------------------
        # e.g. "compress folder Project to project.tar.gz", "tar folder Project to project.tar.gz"
        m = re.search(r"^(?:please\s+)?(?:compress|tar|zip|archive)\s+(?:folder\s+|dir\s+|directory\s+|file\s+)?['\"]?(?P<src>[a-zA-Z0-9_\-\.\/~]+)['\"]?\s+(?:to|into|as)\s+['\"]?(?P<dest>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            src = m.group("src").strip()
            dest = m.group("dest").strip()
            if dest.endswith((".tar.gz", ".tgz")):
                cmd = f"tar -czf '{dest}' '{src}'"
            elif dest.endswith(".tar.bz2"):
                cmd = f"tar -cjf '{dest}' '{src}'"
            elif dest.endswith(".tar"):
                cmd = f"tar -cf '{dest}' '{src}'"
            elif dest.endswith(".zip"):
                cmd = f"zip -r '{dest}' '{src}'"
            else:
                dest = f"{dest}.tar.gz"
                cmd = f"tar -czf '{dest}' '{src}'"
            return {
                "command": cmd,
                "src": src,
                "dest": dest,
                "description": f"Compresses '{src}' into archive '{dest}'.",
                "intent": "archive_create",
                "safety_level": "MODIFYING",
                "risk_score": 0.25,
                "rollback_command": f"rm -f '{dest}'",
                "explanation": f"I will compress '{src}' into '{dest}'.",
                "explanation_paragraph": f"The assistant prepared the archive command `{cmd}` to pack and compress the target into `{dest}`."
            }

        # e.g. "extract archive project.tar.gz to /tmp", "unzip data.zip to /tmp", "extract data.zip"
        m = re.search(r"^(?:please\s+)?(?:extract|uncompress|untar|unzip|decompress)\s+(?:archive\s+|file\s+)?['\"]?(?P<src>[a-zA-Z0-9_\-\.\/~]+)['\"]?(?:\s+(?:to|into|in)\s+['\"]?(?P<dest>[a-zA-Z0-9_\-\.\/~]+)['\"]?)?$", clean, re.IGNORECASE)
        if m:
            src = m.group("src").strip()
            dest = (m.group("dest") or ".").strip()
            if src.endswith((".tar.gz", ".tgz")):
                cmd = f"mkdir -p '{dest}' && tar -xzf '{src}' -C '{dest}'"
            elif src.endswith(".tar.bz2"):
                cmd = f"mkdir -p '{dest}' && tar -xjf '{src}' -C '{dest}'"
            elif src.endswith(".tar"):
                cmd = f"mkdir -p '{dest}' && tar -xf '{src}' -C '{dest}'"
            elif src.endswith(".zip"):
                cmd = f"mkdir -p '{dest}' && unzip -q '{src}' -d '{dest}'"
            else:
                cmd = f"mkdir -p '{dest}' && tar -xf '{src}' -C '{dest}'"
            return {
                "command": cmd,
                "src": src,
                "dest": dest,
                "description": f"Extracts archive '{src}' into '{dest}'.",
                "intent": "archive_extract",
                "safety_level": "MODIFYING",
                "risk_score": 0.30,
                "rollback_command": None,
                "explanation": f"I will extract archive '{src}' into '{dest}'.",
                "explanation_paragraph": f"The assistant compiled your request into `{cmd}`, unpacking the contents into the destination folder."
            }

        # ---------------------------------------------------------------------
        # 5. Advanced File Search & Discovery
        # ---------------------------------------------------------------------
        # e.g. "find all pdf files in Downloads", "find all python files in src"
        m = re.search(r"^(?:please\s+)?(?:find|show|list|search\s+for)\s+(?:all\s+)?(?P<ext>[a-zA-Z0-9]+)\s+files\s+(?:in|under|inside)\s+['\"]?(?P<dir>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            ext = m.group("ext").lower().lstrip(".")
            t_dir = os.path.expanduser(m.group("dir").strip())
            cmd = f"find '{t_dir}' -type f -iname '*.{ext}' 2>/dev/null"
            return {
                "command": cmd,
                "description": f"Searches '{t_dir}' for all .{ext} files.",
                "intent": "file_find",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will find all .{ext} files in '{t_dir}'.",
                "explanation_paragraph": f"The assistant queried the filesystem using `find '{t_dir}' -type f -iname '*.{ext}'` to locate matching files."
            }

        # e.g. "find files larger than 100MB in Downloads", "find big files in ~"
        m = re.search(r"^(?:please\s+)?find\s+files\s+larger\s+than\s+(?P<size>[0-9]+)\s*(?P<unit>mb|gb|kb|m|g|k)?\s+(?:in|under|inside)\s+['\"]?(?P<dir>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            size = m.group("size")
            unit = (m.group("unit") or "M").upper()[0]
            t_dir = os.path.expanduser(m.group("dir").strip())
            cmd = f"find '{t_dir}' -type f -size +{size}{unit} -exec ls -lh {{}} + 2>/dev/null | sort -k5 -rh"
            return {
                "command": cmd,
                "description": f"Finds files larger than {size}{unit} in '{t_dir}'.",
                "intent": "storage_find_large",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will find files larger than {size}{unit} in '{t_dir}'.",
                "explanation_paragraph": f"The assistant compiled a search filter for files exceeding {size}{unit} in `{t_dir}`."
            }

        # e.g. "search for 'TODO' in src", "search for text 'error' in logs"
        m = re.search(r"^(?:please\s+)?search\s+(?:for\s+)?(?:text|string|pattern|word)?\s*['\"](?P<pattern>[^'\"]+)['\"]\s+(?:in|under|inside)\s+['\"]?(?P<dir>[a-zA-Z0-9_\-\.\/~]+)['\"]?$", clean, re.IGNORECASE)
        if m:
            pat = m.group("pattern").strip()
            t_dir = os.path.expanduser(m.group("dir").strip())
            cmd = f"grep -rnI '{pat}' '{t_dir}' 2>/dev/null | head -n 30"
            return {
                "command": cmd,
                "description": f"Searches for '{pat}' inside files in '{t_dir}'.",
                "intent": "file_find",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will search for text '{pat}' in '{t_dir}'.",
                "explanation_paragraph": f"The assistant compiled `grep -rnI '{pat}' '{t_dir}' | head -n 30` to search matching file contents."
            }

        # ---------------------------------------------------------------------
        # 6. Git & Developer Operations
        # ---------------------------------------------------------------------
        if re.search(r"^(?:git\s+status|show\s+git\s+status|check\s+git\s+status)$", clean, re.IGNORECASE):
            cmd = "git status"
            return {
                "command": cmd,
                "description": "Shows working tree status in the active Git repository.",
                "intent": "git_status",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will display the current git working tree status.",
                "explanation_paragraph": "The assistant executed `git status` to check staged, unstaged, and untracked changes."
            }

        if re.search(r"^(?:git\s+branch|show\s+git\s+branch(?:es)?|list\s+git\s+branch(?:es)?)$", clean, re.IGNORECASE):
            cmd = "git branch -a"
            return {
                "command": cmd,
                "description": "Lists local and remote Git branches.",
                "intent": "git_branch",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will list all active Git branches.",
                "explanation_paragraph": "The assistant executed `git branch -a`."
            }

        if re.search(r"^(?:git\s+log|show\s+git\s+log|show\s+recent\s+commits?)$", clean, re.IGNORECASE):
            cmd = "git log --oneline -n 15"
            return {
                "command": cmd,
                "description": "Displays the last 15 Git commit logs.",
                "intent": "git_log",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will display the recent Git commit history.",
                "explanation_paragraph": "The assistant executed `git log --oneline -n 15`."
            }

        if re.search(r"^(?:git\s+pull|pull\s+latest\s+changes?)$", clean, re.IGNORECASE):
            cmd = "git pull"
            return {
                "command": cmd,
                "description": "Fetches and integrates changes from the remote repository.",
                "intent": "git_pull",
                "safety_level": "MODIFYING",
                "risk_score": 0.35,
                "explanation": "I will pull the latest changes from the remote repository.",
                "explanation_paragraph": "The assistant executed `git pull`."
            }

        # e.g. "run tests", "run pytest", "execute test suite"
        if re.search(r"^(?:run\s+tests?|run\s+pytest|execute\s+test\s+suite|pytest)$", clean, re.IGNORECASE):
            cmd = "pytest || python3 -m unittest"
            return {
                "command": cmd,
                "description": "Executes automated project test suite using pytest or unittest.",
                "intent": "dev_tests",
                "safety_level": "READ_ONLY",
                "risk_score": 0.10,
                "explanation": "I will execute the project test suite.",
                "explanation_paragraph": "The assistant dispatched `pytest` to run automated test cases."
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

            # Check popular sites dictionary (word boundary match)
            for site_key, site_url in cls.POPULAR_SITES.items():
                if target == site_key or target == f"my {site_key}" or re.search(rf"\b{re.escape(site_key)}\b", target, re.IGNORECASE):
                    if site_key == "x" and ("firefox" in target or "matrix" in target or "linux" in target):
                        continue
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

            # Check standard named folders (e.g. "open downloads", "open my documents folder", "open downlaods")
            cleaned_target = re.sub(r"^(?:my\s+|the\s+)", "", target)
            cleaned_target = re.sub(r"^(?:folder\s+|dir\s+|directory\s+)", "", cleaned_target)
            cleaned_target = re.sub(r"\s+(?:folder|dir|directory)$", "", cleaned_target).strip()
            if cleaned_target in cls.STANDARD_FOLDERS:
                raw_folder = cls.STANDARD_FOLDERS[cleaned_target]
                folder_path = os.path.expanduser(raw_folder)
                cmd = f"xdg-open '{folder_path}'"
                display_name = cleaned_target.capitalize()
                return {
                    "command": cmd,
                    "path": folder_path,
                    "description": f"Opens '{folder_path}' in system file manager.",
                    "intent": "desktop_open_folder",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will open the '{display_name}' folder in your file manager.",
                    "explanation_paragraph": f"The assistant parsed your request to view the {display_name} directory and executed `xdg-open '{folder_path}'` to launch your system's graphical file manager."
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

            # Check arbitrary folder open (e.g. "open my DSA folder", "open folder Divya", "open Divya folder")
            COMMON_SERVICES = {"nginx", "apache2", "docker", "mysql", "mariadb", "postgresql", "redis", "ssh", "sshd", "ufw", "cron", "crond", "systemd", "iptables"}
            if target not in COMMON_SERVICES and not target.endswith(".service"):
                m_folder = re.search(r"^(?:my\s+|the\s+)?(?:folder\s+|dir\s+|directory\s+)?(?P<fld>[a-zA-Z0-9_\-\.\/~ ]+?)(?:\s+(?:folder|dir|directory))?$", orig_target, re.IGNORECASE)
                if m_folder:
                    fld = m_folder.group("fld").strip()
                    if fld.lower() not in COMMON_SERVICES:
                        from ops_assistant.tools.desktop_ops import find_target_folder
                        discovered = find_target_folder(fld)
                        if discovered:
                            target_path = str(discovered)
                            cmd = f"xdg-open '{target_path}'"
                            return {
                                "command": cmd,
                                "path": target_path,
                                "description": f"Opens discovered folder '{target_path}' in system file manager.",
                                "intent": "desktop_open_folder",
                                "safety_level": "READ_ONLY",
                                "risk_score": 0.05,
                                "explanation": f"I discovered the '{fld}' folder at `{target_path}` and will open it.",
                                "explanation_paragraph": f"The assistant scanned your computer, located `{target_path}`, and dispatched `xdg-open '{target_path}'` to reveal it in your file manager."
                            }
                        elif ("folder" in clean.lower() or "dir" in clean.lower() or "directory" in clean.lower() or "/" in fld or fld.startswith("~")):
                            home_target = os.path.expanduser(f"~/{fld}") if not fld.startswith(("/", "~", ".")) else os.path.expanduser(fld)
                            user_home = os.path.expanduser("~")
                            clean_fld = shlex.quote(fld)
                            cmd = f"TARGET=$(find ~ -maxdepth 5 -type d -iname {clean_fld} ! -path '*/.*' ! -path '*/node_modules/*' 2>/dev/null | head -n 1); if [ -n \"$TARGET\" ]; then xdg-open \"$TARGET\"; elif [ -d '{home_target}' ]; then xdg-open '{home_target}'; else xdg-open '{user_home}'; fi"
                            return {
                                "command": cmd,
                                "path": home_target,
                                "description": f"Searches computer for '{fld}' and opens it in default file manager.",
                                "intent": "desktop_open_folder",
                                "safety_level": "READ_ONLY",
                                "risk_score": 0.05,
                                "explanation": f"I will search your computer for '{fld}' and open it in your file manager.",
                                "explanation_paragraph": f"The assistant synthesized a filesystem search command to dynamically find `{fld}` across your directories and open it in your graphical file manager."
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
        if m_del and not any(kw in clean.lower() for kw in ("package", "app", "application", "service", "daemon", "logs", "cache", "temp", "temporary", "trash")):
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
                "intent": "system_battery",
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

        # 8. Root & Superuser Shell Elevation
        if re.search(r"^(?:root|root\s+user|switch\s+to\s+root|login\s+as\s+root|become\s+root|elevate\s+to\s+root|root\s+shell|root\s+terminal|run\s+as\s+root|sudo\s+su|su\s+-?|to\s+root)$", clean, re.IGNORECASE):
            cmd = "sudo -i"
            return {
                "command": cmd,
                "description": "Opens an interactive root superuser login shell.",
                "intent": "system_root_shell",
                "safety_level": "MODIFYING",
                "risk_score": 0.50,
                "explanation": "I will open an interactive root login shell.",
                "explanation_paragraph": "The assistant converted your elevation request into `sudo -i`, launching an interactive login shell with root superuser environment and privileges."
            }

        # 5. Network Information & Public IP
        # e.g. "what is my public ip", "what is my ip"
        if re.search(r"\b(?:what\s+is\s+my|show\s+my|get\s+my|check\s+my)?\s*(?:public\s+ip|external\s+ip|wan\s+ip)\b", clean, re.IGNORECASE):
            cmd = "curl -s https://ifconfig.me || curl -s https://api.ipify.org"
            return {
                "command": cmd,
                "description": "Fetches public WAN IP address from remote resolver.",
                "intent": "network_status",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will fetch your public WAN IP address.",
                "explanation_paragraph": "The assistant queried an external echo service to retrieve your gateway IP."
            }

        if re.search(r"\b(?:what\s+is\s+my|show\s+my|get\s+my|check\s+my)?\s*(?:ip|ip\s+address|network\s+ip|local\s+ip)\b", clean, re.IGNORECASE):
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

        # 9. Move / Copy by File Extension
        # e.g. "move all PDF files into Documents", "move *.pdf to ~/Documents", "copy all images into Pictures"
        m_move_ext = re.search(r"^(?:please\s+)?(?P<action>move|copy)\s+(?:all\s+)?(?:\*\.)?(?P<ext>[a-zA-Z0-9]+)\s+(?:files?\s+)?(?:in|into|to)\s+(?P<dst>[a-zA-Z0-9_\-\.\/~]+)$", clean, re.IGNORECASE)
        if m_move_ext:
            act_verb = m_move_ext.group("action").lower()
            ext = m_move_ext.group("ext").lower()
            dst = os.path.expanduser(m_move_ext.group("dst").strip())
            bin_cmd = "mv" if act_verb == "move" else "cp -r"
            cmd = f"mkdir -p '{dst}' && find . -maxdepth 1 -iname '*.{ext}' -exec {bin_cmd} {{}} '{dst}/' \\;"
            return {
                "command": cmd,
                "description": f"{act_verb.capitalize()}s all .{ext} files into '{dst}'.",
                "intent": f"file_{act_verb}",
                "safety_level": "MODIFYING",
                "risk_score": 0.30,
                "rollback_command": None,
                "explanation": f"I will {act_verb} all .{ext} files into '{dst}'.",
                "explanation_paragraph": f"The assistant compiled your instruction into `mkdir -p '{dst}' && find . -maxdepth 1 -iname '*.{ext}' -exec {bin_cmd} {{}} '{dst}/' \\;`, safely relocating matching .{ext} files into the target folder."
            }

        # 10. Web Search (e.g. "search for Python tutorials", "search google for python tutorials")
        m_search = re.search(r"^(?:please\s+)?search\s+(?:for|google\s+for|on\s+google\s+for|the\s+web\s+for)\s+(?P<query>.+)$", clean, re.IGNORECASE)
        if m_search:
            s_query = m_search.group("query").strip()
            import urllib.parse
            encoded = urllib.parse.quote_plus(s_query)
            search_url = f"https://www.google.com/search?q={encoded}"
            return {
                "command": f"xdg-open '{search_url}'",
                "url": search_url,
                "description": f"Searches Google for '{s_query}' in default web browser.",
                "intent": "desktop_open_browser",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": f"I will search Google for '{s_query}'.",
                "explanation_paragraph": f"The assistant compiled your web search query into `xdg-open '{search_url}'`, launching your default browser directly to the search results."
            }

        # 11. Delete Temporary Files / Clean Cache
        if re.search(r"\b(?:clean|delete|clear|remove|purge)\s+(?:all\s+)?(?:temp|temporary|cache)\s*(?:files|data)?\b", clean, re.IGNORECASE):
            cmd = "rm -rf /tmp/* ~/.cache/* 2>/dev/null || true"
            return {
                "command": cmd,
                "description": "Purges temporary system files and user application cache.",
                "intent": "storage_clean_temp",
                "safety_level": "MODIFYING",
                "risk_score": 0.40,
                "explanation": "I will clean up temporary files in /tmp and ~/.cache.",
                "explanation_paragraph": "The assistant compiled your request into `rm -rf /tmp/* ~/.cache/*`, reclaiming disk capacity by purging transient cache and ephemeral temporary files."
            }

        # 13. Contextual Largest File Deletion / Finding in Specific Directory
        # e.g. "delete the largest file in '/home/god/Downloads'", "find the largest file in '/home/god/Downloads'"
        m_largest = re.search(r"^(?:please\s+)?(?P<action>delete|remove|erase|find|show|locate)\s+(?:the\s+)?(?:largest|biggest)\s+file\s+(?:in|under|inside)\s+['\"]?(?P<dir>[^'\"]+?)['\"]?$", clean, re.IGNORECASE)
        if m_largest:
            action = m_largest.group("action").lower()
            t_dir = os.path.expanduser(m_largest.group("dir").strip())
            if action in ("delete", "remove", "erase"):
                cmd = (
                    f"largest=$(find '{t_dir}' -maxdepth 2 -type f -printf '%s %p\\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-); "
                    f"if [ -n \"$largest\" ]; then rm -f \"$largest\" && echo \"Deleted largest file: $largest\"; "
                    f"else echo \"No files found in {t_dir}\"; fi"
                )
                return {
                    "command": cmd,
                    "path": t_dir,
                    "description": f"Finds and deletes the largest file inside '{t_dir}'.",
                    "intent": "file_delete_largest",
                    "safety_level": "HIGH_RISK",
                    "risk_score": 0.70,
                    "rollback_command": None,
                    "explanation": f"I will locate and delete the largest file in '{t_dir}'.",
                    "explanation_paragraph": f"The assistant resolved your contextual request to `{t_dir}`, located the largest file by byte size, and prepared a safe single-file deletion."
                }
            else:
                cmd = f"find '{t_dir}' -maxdepth 2 -type f -exec ls -lh {{}} + 2>/dev/null | sort -k5 -rh | head -n 10"
                return {
                    "command": cmd,
                    "path": t_dir,
                    "description": f"Lists largest files in '{t_dir}'.",
                    "intent": "file_find_large",
                    "safety_level": "READ_ONLY",
                    "risk_score": 0.05,
                    "explanation": f"I will list the largest files in '{t_dir}'.",
                    "explanation_paragraph": f"The assistant searched `{t_dir}` and formatted the largest files by size."
                }

        # ---------------------------------------------------------------------
        # 14. Battery, GPU & Hardware Sensors
        # ---------------------------------------------------------------------
        if re.search(r"\b(?:check|show|view|get)\s+(?:my\s+)?(?:battery|power|charge)(?:\s+(?:status|percentage|level))?\b", clean, re.IGNORECASE):
            cmd = "upower -i $(upower -e | grep 'BAT' | head -n 1) 2>/dev/null || cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || acpi -b 2>/dev/null || echo 'Battery status unavailable'"
            return {
                "command": cmd,
                "description": "Queries battery charge level and power supply state.",
                "intent": "system_battery",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will check your battery status and charge percentage.",
                "explanation_paragraph": "The assistant inspected hardware power supplies using upower/sysfs."
            }

        if re.search(r"\b(?:check|show|view|get)\s+(?:my\s+)?(?:gpu|graphics|vram|nvidia)(?:\s+(?:info|status|usage|specs))?\b", clean, re.IGNORECASE):
            cmd = "nvidia-smi 2>/dev/null || lspci | grep -i -E 'vga|3d|display' || echo 'No dedicated GPU utility detected'"
            return {
                "command": cmd,
                "description": "Displays GPU hardware acceleration and VRAM statistics.",
                "intent": "hardware_profile",
                "safety_level": "READ_ONLY",
                "risk_score": 0.05,
                "explanation": "I will inspect your graphics card and GPU statistics.",
                "explanation_paragraph": "The assistant queried GPU state using `nvidia-smi` and PCI device scans."
            }

        return None


def generate_natural_explanation(query: str, command: str, returncode: int = 0, stdout: str = "", stderr: str = "") -> str:
    """
    Generates a clear, informative natural language explanation paragraph for any command.
    Explains the purpose, impact on the filesystem/system, and execution outcome.
    """
    from ops_assistant.explainer.xai import ExecutionOutcomeExplainer
    res = ExecutionOutcomeExplainer.explain_outcome(
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        query=query
    )
    return res.get("natural_explanation") or res.get("explanation_paragraph", f"Executed `{command}` with exit code {returncode}.")

