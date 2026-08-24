"""
Entity Extractor for LinuxOpsAssistant Natural Language Understanding.

Extracts structured domain parameters (paths, extensions, sizes, process names,
ports, URLs, git branches) from natural language requests.
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ExtractedEntities:
    """Holds parsed domain parameters extracted from an utterance."""
    target_path: Optional[str] = None
    destination_path: Optional[str] = None
    folder_name: Optional[str] = None
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    size_filter: Optional[str] = None
    time_filter: Optional[str] = None
    process_name: Optional[str] = None
    pid: Optional[int] = None
    service_name: Optional[str] = None
    port: Optional[int] = None
    package_name: Optional[str] = None
    git_branch: Optional[str] = None
    url: Optional[str] = None
    is_recursive: bool = False
    raw_entities: Dict[str, Any] = field(default_factory=dict)


class EntityExtractor:
    """Extracts Linux sysadmin entities using regex and heuristic models."""

    SIZE_PATTERN = re.compile(r"\b(?:larger\s+than|greater\s+than|over|above|size\s*\+?)\s*([0-9]+(?:\.[0-9]+)?\s*(?:k|kb|m|mb|g|gb|bytes?))\b", re.IGNORECASE)
    EXT_PATTERN = re.compile(r"\b(?:\*\.|\.)([a-zA-Z0-9_]{1,10})\s*(?:files?|documents?|videos?|images?)?\b", re.IGNORECASE)
    PORT_PATTERN = re.compile(r"\b(?:port|on\s+port|listening\s+on)\s*([0-9]{2,5})\b", re.IGNORECASE)
    PID_PATTERN = re.compile(r"\b(?:pid|process\s+id)\s*([0-9]{1,7})\b", re.IGNORECASE)
    URL_PATTERN = re.compile(r"(https?://[^\s\"']+|www\.[^\s\"']+|[a-zA-Z0-9-]+\.(?:com|org|io|net|in|dev|edu)(?:/[^\s\"']*)?)", re.IGNORECASE)

    @classmethod
    def extract(cls, query: str, active_directory: Optional[str] = None) -> ExtractedEntities:
        """Extracts all domain entities present in a query."""
        entities = ExtractedEntities()
        raw: Dict[str, Any] = {}
        q = query.strip()

        # 1. URL extraction
        url_match = cls.URL_PATTERN.search(q)
        if url_match:
            entities.url = url_match.group(1)
            raw["url"] = entities.url

        # 2. Port extraction
        port_match = cls.PORT_PATTERN.search(q)
        if port_match:
            try:
                entities.port = int(port_match.group(1))
                raw["port"] = entities.port
            except ValueError:
                pass

        # 3. PID extraction
        pid_match = cls.PID_PATTERN.search(q)
        if pid_match:
            try:
                entities.pid = int(pid_match.group(1))
                raw["pid"] = entities.pid
            except ValueError:
                pass

        # 4. Size Filter extraction
        size_match = cls.SIZE_PATTERN.search(q)
        if size_match:
            entities.size_filter = size_match.group(1).replace(" ", "")
            raw["size_filter"] = entities.size_filter

        # 5. File Extension extraction (e.g. "all PDF files", "*.mp4", "python files")
        ext_match = cls.EXT_PATTERN.search(q)
        if ext_match:
            ext = ext_match.group(1).lower()
            if ext in ("pdf", "png", "jpg", "jpeg", "mp4", "mp3", "py", "sh", "txt", "csv", "json", "log", "tar", "gz", "zip", "deb", "pkg"):
                entities.file_extension = f".{ext}"
                raw["file_extension"] = entities.file_extension
        elif "python" in q.lower() and "file" in q.lower():
            entities.file_extension = ".py"
            raw["file_extension"] = ".py"

        # 6. Folder name extraction (e.g. "folder called Projects", "create directory DSA")
        folder_match = re.search(r"\b(?:folder|directory|dir)\s+(?:called|named)?\s*['\"]?([a-zA-Z0-9_\-\.\/]+)['\"]?", q, re.IGNORECASE)
        if folder_match:
            entities.folder_name = folder_match.group(1)
            raw["folder_name"] = entities.folder_name

        # 7. Move/Copy Source & Destination extraction (e.g. "Move all PDF files into Documents")
        move_match = re.search(r"\b(?:move|copy)\s+(?P<src>.+?)\s+(?:to|into|in)\s+(?P<dst>[a-zA-Z0-9_\-\.\/~]+)\b", q, re.IGNORECASE)
        if move_match:
            entities.target_path = move_match.group("src").strip()
            entities.destination_path = move_match.group("dst").strip()
            raw["source"] = entities.target_path
            raw["destination"] = entities.destination_path

        entities.raw_entities = raw
        return entities
