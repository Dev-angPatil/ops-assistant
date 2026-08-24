"""
Knowledge base and cross-distribution software catalog for the AI-Powered Installer.
Contains mappings for 100+ desktop applications, developer tools, runtimes, and libraries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from ops_assistant.installer.models import InstallTargetType, InstallSource


# ---------------------------------------------------------------------------
# 1. Desktop Applications & Dev Tools Catalog
# ---------------------------------------------------------------------------

APP_CATALOG: Dict[str, Dict[str, Any]] = {
    # Desktop Apps
    "vscode": {
        "name": "Visual Studio Code",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Code editor redefined and optimized for building and debugging modern web and cloud applications.",
        "launch_cmd": "code",
        "packages": {
            "arch": {"pacman": "code", "aur": "visual-studio-code-bin"},
            "debian": {"apt": "code", "deb_url": "https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64"},
            "rhel": {"dnf": "code"},
            "opensuse": {"zypper": "code"},
            "alpine": {"flatpak": "com.visualstudio.code"},
        },
        "flatpak": "com.visualstudio.code",
        "snap": "code --classic",
    },
    "whatsapp": {
        "name": "WhatsApp for Linux",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Desktop client for WhatsApp messaging with native system notifications and tray integration.",
        "launch_cmd": "whatsapp-for-linux",
        "packages": {
            "arch": {"aur": "whatsapp-for-linux", "flatpak": "com.github.eneshecan.WhatsAppForLinux"},
            "debian": {"flatpak": "com.github.eneshecan.WhatsAppForLinux", "snap": "whatsapp-for-linux"},
            "rhel": {"flatpak": "com.github.eneshecan.WhatsAppForLinux"},
            "opensuse": {"flatpak": "com.github.eneshecan.WhatsAppForLinux"},
            "alpine": {"flatpak": "com.github.eneshecan.WhatsAppForLinux"},
        },
        "flatpak": "com.github.eneshecan.WhatsAppForLinux",
        "snap": "whatsapp-for-linux",
    },
    "chrome": {
        "name": "Google Chrome",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Fast, secure, and customizable web browser built by Google.",
        "launch_cmd": "google-chrome-stable",
        "packages": {
            "arch": {"aur": "google-chrome", "pacman": "chromium"},
            "debian": {"apt": "chromium", "deb_url": "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"},
            "rhel": {"dnf": "google-chrome-stable", "flatpak": "com.google.Chrome"},
            "opensuse": {"zypper": "google-chrome-stable"},
            "alpine": {"apk": "chromium"},
        },
        "flatpak": "com.google.Chrome",
    },
    "chromium": {
        "name": "Chromium Web Browser",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Open-source browser project that powers Google Chrome.",
        "launch_cmd": "chromium",
        "packages": {
            "arch": {"pacman": "chromium"},
            "debian": {"apt": "chromium-browser"},
            "rhel": {"dnf": "chromium"},
            "opensuse": {"zypper": "chromium"},
            "alpine": {"apk": "chromium"},
        },
        "flatpak": "org.chromium.Chromium",
    },
    "discord": {
        "name": "Discord",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Voice, video, and text communication service for gaming and developer communities.",
        "launch_cmd": "discord",
        "packages": {
            "arch": {"pacman": "discord"},
            "debian": {"apt": "discord", "deb_url": "https://discord.com/api/download?platform=linux&format=deb"},
            "rhel": {"dnf": "discord", "flatpak": "com.discordapp.Discord"},
            "opensuse": {"flatpak": "com.discordapp.Discord"},
            "alpine": {"flatpak": "com.discordapp.Discord"},
        },
        "flatpak": "com.discordapp.Discord",
        "snap": "discord",
    },
    "spotify": {
        "name": "Spotify",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Digital music, podcast, and streaming service.",
        "launch_cmd": "spotify",
        "packages": {
            "arch": {"aur": "spotify", "flatpak": "com.spotify.Client"},
            "debian": {"apt": "spotify-client", "flatpak": "com.spotify.Client", "snap": "spotify"},
            "rhel": {"flatpak": "com.spotify.Client"},
            "opensuse": {"flatpak": "com.spotify.Client"},
            "alpine": {"flatpak": "com.spotify.Client"},
        },
        "flatpak": "com.spotify.Client",
        "snap": "spotify",
    },
    "telegram": {
        "name": "Telegram Desktop",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Fast and secure cloud-based mobile and desktop messaging app.",
        "launch_cmd": "telegram-desktop",
        "packages": {
            "arch": {"pacman": "telegram-desktop"},
            "debian": {"apt": "telegram-desktop"},
            "rhel": {"dnf": "telegram-desktop"},
            "opensuse": {"zypper": "telegram-desktop"},
            "alpine": {"apk": "telegram-desktop"},
        },
        "flatpak": "org.telegram.desktop",
    },
    "vlc": {
        "name": "VLC Media Player",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Free and open-source cross-platform multimedia player and streaming media server.",
        "launch_cmd": "vlc",
        "packages": {
            "arch": {"pacman": "vlc"},
            "debian": {"apt": "vlc"},
            "rhel": {"dnf": "vlc"},
            "opensuse": {"zypper": "vlc"},
            "alpine": {"apk": "vlc"},
        },
        "flatpak": "org.videolan.VLC",
    },
    "obs_studio": {
        "name": "OBS Studio",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Free and open source software for video recording and live streaming.",
        "launch_cmd": "obs",
        "packages": {
            "arch": {"pacman": "obs-studio"},
            "debian": {"apt": "obs-studio"},
            "rhel": {"dnf": "obs-studio"},
            "opensuse": {"zypper": "obs-studio"},
            "alpine": {"apk": "obs-studio"},
        },
        "flatpak": "com.obsproject.Studio",
    },
    "android_studio": {
        "name": "Android Studio",
        "category": InstallTargetType.DEV_TOOL,
        "description": "The official Integrated Development Environment (IDE) for Google Android app development.",
        "launch_cmd": "android-studio",
        "packages": {
            "arch": {"aur": "android-studio", "flatpak": "com.google.AndroidStudio"},
            "debian": {"flatpak": "com.google.AndroidStudio", "snap": "android-studio --classic"},
            "rhel": {"flatpak": "com.google.AndroidStudio"},
            "opensuse": {"flatpak": "com.google.AndroidStudio"},
            "alpine": {"flatpak": "com.google.AndroidStudio"},
        },
        "flatpak": "com.google.AndroidStudio",
        "snap": "android-studio --classic",
    },
    "gimp": {
        "name": "GIMP",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "GNU Image Manipulation Program for photo retouching, image composition, and authoring.",
        "launch_cmd": "gimp",
        "packages": {
            "arch": {"pacman": "gimp"},
            "debian": {"apt": "gimp"},
            "rhel": {"dnf": "gimp"},
            "opensuse": {"zypper": "gimp"},
            "alpine": {"apk": "gimp"},
        },
        "flatpak": "org.gimp.GIMP",
    },
    "steam": {
        "name": "Steam",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Digital gaming distribution platform and gaming community hub.",
        "launch_cmd": "steam",
        "packages": {
            "arch": {"pacman": "steam"},
            "debian": {"apt": "steam-installer"},
            "rhel": {"dnf": "steam"},
            "opensuse": {"zypper": "steam"},
            "alpine": {"flatpak": "com.valvesoftware.Steam"},
        },
        "flatpak": "com.valvesoftware.Steam",
    },
    "postman": {
        "name": "Postman",
        "category": InstallTargetType.DEV_TOOL,
        "description": "API platform for building and using APIs and automated endpoint testing.",
        "launch_cmd": "postman",
        "packages": {
            "arch": {"aur": "postman-bin", "flatpak": "com.getpostman.Postman"},
            "debian": {"flatpak": "com.getpostman.Postman", "snap": "postman"},
            "rhel": {"flatpak": "com.getpostman.Postman"},
            "opensuse": {"flatpak": "com.getpostman.Postman"},
            "alpine": {"flatpak": "com.getpostman.Postman"},
        },
        "flatpak": "com.getpostman.Postman",
        "snap": "postman",
    },
    "slack": {
        "name": "Slack Desktop",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Team communication, channels, and enterprise collaboration tool.",
        "launch_cmd": "slack",
        "packages": {
            "arch": {"aur": "slack-desktop", "flatpak": "com.slack.Slack"},
            "debian": {"flatpak": "com.slack.Slack", "snap": "slack --classic"},
            "rhel": {"flatpak": "com.slack.Slack"},
            "opensuse": {"flatpak": "com.slack.Slack"},
            "alpine": {"flatpak": "com.slack.Slack"},
        },
        "flatpak": "com.slack.Slack",
        "snap": "slack --classic",
    },

    # Developer Tools, Runtimes & Infrastructure
    "docker": {
        "name": "Docker CE & Compose",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Container virtualization engine for building, sharing, and running distributed applications.",
        "launch_cmd": "docker --version",
        "packages": {
            "arch": {"pacman": "docker docker-compose"},
            "debian": {"apt": "docker.io docker-compose"},
            "rhel": {"dnf": "docker-ce docker-ce-cli containerd.io docker-compose-plugin"},
            "opensuse": {"zypper": "docker docker-compose"},
            "alpine": {"apk": "docker docker-compose"},
        },
        "post_install_services": ["docker"],
        "post_install_group": "docker",
    },
    "git": {
        "name": "Git",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Fast, scalable, distributed revision control system.",
        "launch_cmd": "git --version",
        "packages": {
            "arch": {"pacman": "git"},
            "debian": {"apt": "git"},
            "rhel": {"dnf": "git"},
            "opensuse": {"zypper": "git"},
            "alpine": {"apk": "git"},
        },
    },
    "python": {
        "name": "Python 3 & Pip",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Modern, versatile high-level programming language and package manager.",
        "launch_cmd": "python3 --version",
        "packages": {
            "arch": {"pacman": "python python-pip python-virtualenv"},
            "debian": {"apt": "python3 python3-pip python3-venv python3-dev"},
            "rhel": {"dnf": "python3 python3-pip python3-devel"},
            "opensuse": {"zypper": "python3 python3-pip python3-devel"},
            "alpine": {"apk": "python3 py3-pip python3-dev"},
        },
    },
    "nodejs": {
        "name": "Node.js & npm",
        "category": InstallTargetType.DEV_TOOL,
        "description": "JavaScript runtime built on Chrome's V8 engine with npm package manager.",
        "launch_cmd": "node -v",
        "packages": {
            "arch": {"pacman": "nodejs npm"},
            "debian": {"apt": "nodejs npm"},
            "rhel": {"dnf": "nodejs npm"},
            "opensuse": {"zypper": "nodejs npm"},
            "alpine": {"apk": "nodejs npm"},
        },
    },
    "java": {
        "name": "Java OpenJDK (LTS)",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Open-source implementation of the Java Platform, Standard Edition.",
        "launch_cmd": "java -version",
        "packages": {
            "arch": {"pacman": "jdk-openjdk"},
            "debian": {"apt": "default-jdk"},
            "rhel": {"dnf": "java-latest-openjdk-devel"},
            "opensuse": {"zypper": "java-17-openjdk-devel"},
            "alpine": {"apk": "openjdk17"},
        },
    },
    "java_21": {
        "name": "Java OpenJDK 21 LTS",
        "category": InstallTargetType.DEV_TOOL,
        "description": "OpenJDK 21 Long Term Support edition for enterprise Java workloads.",
        "launch_cmd": "java -version",
        "packages": {
            "arch": {"pacman": "jdk21-openjdk"},
            "debian": {"apt": "openjdk-21-jdk"},
            "rhel": {"dnf": "java-21-openjdk-devel"},
            "opensuse": {"zypper": "java-21-openjdk-devel"},
            "alpine": {"apk": "openjdk21"},
        },
    },
    "rust": {
        "name": "Rust & Cargo",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Blazingly fast and memory-efficient systems programming language.",
        "launch_cmd": "rustc --version",
        "packages": {
            "arch": {"pacman": "rust cargo"},
            "debian": {"apt": "rustc cargo"},
            "rhel": {"dnf": "rust cargo"},
            "opensuse": {"zypper": "rust cargo"},
            "alpine": {"apk": "rust cargo"},
        },
    },
    "golang": {
        "name": "Go (Golang)",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Open source programming language that makes it easy to build simple, reliable, and efficient software.",
        "launch_cmd": "go version",
        "packages": {
            "arch": {"pacman": "go"},
            "debian": {"apt": "golang"},
            "rhel": {"dnf": "golang"},
            "opensuse": {"zypper": "go"},
            "alpine": {"apk": "go"},
        },
    },
    "mysql": {
        "name": "MySQL Server / MariaDB",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Popular relational database management system.",
        "launch_cmd": "mysql --version",
        "packages": {
            "arch": {"pacman": "mariadb"},
            "debian": {"apt": "mysql-server"},
            "rhel": {"dnf": "mariadb-server"},
            "opensuse": {"zypper": "mariadb"},
            "alpine": {"apk": "mariadb mariadb-client"},
        },
        "post_install_services": ["mariadb", "mysql"],
    },
    "postgresql": {
        "name": "PostgreSQL Server",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Powerful, open-source object-relational database system.",
        "launch_cmd": "psql --version",
        "packages": {
            "arch": {"pacman": "postgresql"},
            "debian": {"apt": "postgresql postgresql-contrib"},
            "rhel": {"dnf": "postgresql-server postgresql-contrib"},
            "opensuse": {"zypper": "postgresql-server"},
            "alpine": {"apk": "postgresql"},
        },
        "post_install_services": ["postgresql"],
    },
    "redis": {
        "name": "Redis In-Memory Store",
        "category": InstallTargetType.DEV_TOOL,
        "description": "In-memory data structure store used as a database, cache, and message broker.",
        "launch_cmd": "redis-cli ping",
        "packages": {
            "arch": {"pacman": "redis"},
            "debian": {"apt": "redis-server"},
            "rhel": {"dnf": "redis"},
            "opensuse": {"zypper": "redis"},
            "alpine": {"apk": "redis"},
        },
        "post_install_services": ["redis", "redis-server"],
    },
    "nginx": {
        "name": "NGINX HTTP & Reverse Proxy Server",
        "category": InstallTargetType.DEV_TOOL,
        "description": "High-performance HTTP server and reverse proxy.",
        "launch_cmd": "nginx -v",
        "packages": {
            "arch": {"pacman": "nginx"},
            "debian": {"apt": "nginx"},
            "rhel": {"dnf": "nginx"},
            "opensuse": {"zypper": "nginx"},
            "alpine": {"apk": "nginx"},
        },
        "post_install_services": ["nginx"],
    },
    "cuda": {
        "name": "NVIDIA CUDA Toolkit",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Parallel computing platform and programming model for GPU-accelerated computing.",
        "launch_cmd": "nvcc --version",
        "packages": {
            "arch": {"pacman": "cuda"},
            "debian": {"apt": "nvidia-cuda-toolkit"},
            "rhel": {"dnf": "cuda-toolkit"},
            "opensuse": {"zypper": "cuda"},
            "alpine": {"apk": "cuda"},
        },
    },
    "build_essential": {
        "name": "C/C++ Build Essentials & Compilers",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Core GNU C/C++ compiler toolchain (gcc, g++, make, libc-dev).",
        "launch_cmd": "gcc --version",
        "packages": {
            "arch": {"pacman": "base-devel gcc make cmake clang"},
            "debian": {"apt": "build-essential gcc g++ make cmake clang"},
            "rhel": {"dnf": "gcc gcc-c++ make cmake clang groupinstall 'Development Tools'"},
            "opensuse": {"zypper": "gcc gcc-c++ make cmake clang patterns-devel-base-devel_basis"},
            "alpine": {"apk": "build-base gcc g++ make cmake clang"},
        },
    },
    "neovim": {
        "name": "Neovim",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Hyperextensible Vim-based text editor built for high configurability and plugins.",
        "launch_cmd": "nvim",
        "packages": {
            "arch": {"pacman": "neovim"},
            "debian": {"apt": "neovim"},
            "rhel": {"dnf": "neovim"},
            "opensuse": {"zypper": "neovim"},
            "alpine": {"apk": "neovim"},
        },
        "flatpak": "io.neovim.nvim",
    },
    "tmux": {
        "name": "tmux Terminal Multiplexer",
        "category": InstallTargetType.DEV_TOOL,
        "description": "Terminal multiplexer enabling multiple terminal sessions within a single window.",
        "launch_cmd": "tmux -V",
        "packages": {
            "arch": {"pacman": "tmux"},
            "debian": {"apt": "tmux"},
            "rhel": {"dnf": "tmux"},
            "opensuse": {"zypper": "tmux"},
            "alpine": {"apk": "tmux"},
        },
    },
    "htop": {
        "name": "htop Process Viewer",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Interactive process viewer and system monitor.",
        "launch_cmd": "htop",
        "packages": {
            "arch": {"pacman": "htop"},
            "debian": {"apt": "htop"},
            "rhel": {"dnf": "htop"},
            "opensuse": {"zypper": "htop"},
            "alpine": {"apk": "htop"},
        },
    },
    "fastfetch": {
        "name": "Fastfetch System Info",
        "category": InstallTargetType.SYSTEM_APP,
        "description": "Fast, highly customizable system information utility.",
        "launch_cmd": "fastfetch",
        "packages": {
            "arch": {"pacman": "fastfetch"},
            "debian": {"apt": "fastfetch", "ppa": "ppa:zhangsongcui3371/fastfetch"},
            "rhel": {"dnf": "fastfetch"},
            "opensuse": {"zypper": "fastfetch"},
            "alpine": {"apk": "fastfetch"},
        },
    },
}


# ---------------------------------------------------------------------------
# 2. Natural Language App Aliases
# ---------------------------------------------------------------------------

APP_ALIASES: Dict[str, str] = {
    # VS Code
    "vscode": "vscode",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "vsc": "vscode",

    # WhatsApp
    "whatsapp": "whatsapp",
    "whats app": "whatsapp",
    "whatsapp-for-linux": "whatsapp",
    "whatsapp desktop": "whatsapp",
    "zapzap": "whatsapp",

    # Chrome / Chromium
    "chrome": "chrome",
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "chromium": "chromium",
    "chromium browser": "chromium",

    # Docker
    "docker": "docker",
    "docker engine": "docker",
    "docker compose": "docker",
    "docker-compose": "docker",

    # Git
    "git": "git",
    "git scm": "git",

    # Python
    "python": "python",
    "python3": "python",
    "python 3": "python",
    "pip": "python",
    "pip3": "python",

    # Node.js
    "node": "nodejs",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "npm": "nodejs",

    # Java
    "java": "java",
    "openjdk": "java",
    "jdk": "java",
    "java 21": "java_21",
    "java21": "java_21",
    "openjdk 21": "java_21",
    "jdk 21": "java_21",

    # Rust
    "rust": "rust",
    "cargo": "rust",
    "rustc": "rust",

    # Go
    "go": "golang",
    "golang": "golang",

    # Databases
    "mysql": "mysql",
    "mariadb": "mysql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "psql": "postgresql",
    "redis": "redis",

    # Desktop Apps
    "discord": "discord",
    "spotify": "spotify",
    "telegram": "telegram",
    "telegram desktop": "telegram",
    "vlc": "vlc",
    "vlc player": "vlc",
    "vlc media player": "vlc",
    "obs": "obs_studio",
    "obs studio": "obs_studio",
    "android studio": "android_studio",
    "android-studio": "android_studio",
    "gimp": "gimp",
    "steam": "steam",
    "postman": "postman",
    "slack": "slack",

    # GPU / Compilers
    "cuda": "cuda",
    "cuda toolkit": "cuda",
    "nvidia cuda": "cuda",
    "gcc": "build_essential",
    "g++": "build_essential",
    "make": "build_essential",
    "cmake": "build_essential",
    "build essential": "build_essential",
    "build-essential": "build_essential",
    "base-devel": "build_essential",
    "c compiler": "build_essential",
    "c++ compiler": "build_essential",

    # Utilities
    "neovim": "neovim",
    "nvim": "neovim",
    "tmux": "tmux",
    "htop": "htop",
    "fastfetch": "fastfetch",
    "nginx": "nginx",
}


# ---------------------------------------------------------------------------
# 3. Natural Language Library & Concept Map
# ---------------------------------------------------------------------------

NL_LIBRARY_MAP: List[Dict[str, Any]] = [
    {
        "keywords": ["excel", "xlsx", "xls", "spreadsheet", "csv to excel"],
        "target_name": "Excel Processing Libraries",
        "packages": {
            "python": ["openpyxl", "pandas"],
            "node": ["xlsx", "exceljs"],
        },
        "description": "High-performance libraries for reading, creating, and modifying Microsoft Excel (.xlsx/.xls) spreadsheets.",
    },
    {
        "keywords": ["pdf", "read pdf", "parse pdf", "pdf reader", "extract pdf"],
        "target_name": "PDF Processing Libraries",
        "packages": {
            "python": ["pypdf", "pdfplumber"],
            "node": ["pdf-parse"],
        },
        "description": "Libraries for parsing, extracting text/tables, and generating PDF documents.",
    },
    {
        "keywords": ["http", "api request", "requests", "rest client", "fetch data", "curl in python"],
        "target_name": "HTTP / REST Client Libraries",
        "packages": {
            "python": ["requests", "httpx"],
            "node": ["axios"],
        },
        "description": "HTTP client libraries for consuming REST APIs and sending network requests.",
    },
    {
        "keywords": ["chart", "charts", "graphs", "graphing", "plot", "plotting", "data visualization"],
        "target_name": "Data Visualization & Plotting Libraries",
        "packages": {
            "python": ["matplotlib", "seaborn", "plotly"],
            "node": ["chart.js"],
        },
        "description": "Comprehensive libraries for creating static, animated, and interactive data plots and visualizations.",
    },
    {
        "keywords": ["fastapi", "rest api", "backend api", "web server in python", "uvicorn"],
        "target_name": "FastAPI & Uvicorn Async Web Framework",
        "packages": {
            "python": ["fastapi", "uvicorn[standard]"],
            "node": ["express"],
        },
        "description": "Modern, fast (high-performance) web framework for building APIs with Python 3.8+ based on standard Python type hints.",
    },
    {
        "keywords": ["flask", "lightweight web framework"],
        "target_name": "Flask Web Framework",
        "packages": {
            "python": ["flask", "gunicorn"],
            "node": ["express"],
        },
        "description": "Lightweight WSGI web application framework for Python.",
    },
    {
        "keywords": ["django"],
        "target_name": "Django Web Framework",
        "packages": {
            "python": ["django"],
        },
        "description": "High-level Python web framework that encourages rapid development and clean, pragmatic design.",
    },
    {
        "keywords": ["react", "reactjs", "react.js"],
        "target_name": "React Frontend Framework",
        "packages": {
            "node": ["react", "react-dom"],
        },
        "description": "The library for web and native user interfaces.",
    },
    {
        "keywords": ["vue", "vuejs", "vue.js"],
        "target_name": "Vue.js Framework",
        "packages": {
            "node": ["vue"],
        },
        "description": "Progressive JavaScript Framework for building modern web UI.",
    },
    {
        "keywords": ["express", "expressjs"],
        "target_name": "Express.js Web Server",
        "packages": {
            "node": ["express"],
        },
        "description": "Fast, unopinionated, minimalist web framework for Node.js.",
    },
    {
        "keywords": ["tailwind", "tailwindcss"],
        "target_name": "Tailwind CSS",
        "packages": {
            "node": ["tailwindcss", "postcss", "autoprefixer"],
        },
        "description": "Utility-first CSS framework for rapid UI development.",
    },
    {
        "keywords": ["tensorflow", "deep learning", "neural network"],
        "target_name": "TensorFlow Machine Learning Engine",
        "packages": {
            "python": ["tensorflow"],
        },
        "description": "End-to-end open source platform for machine learning and neural networks.",
    },
    {
        "keywords": ["pytorch", "torch"],
        "target_name": "PyTorch Deep Learning Framework",
        "packages": {
            "python": ["torch", "torchvision", "torchaudio"],
        },
        "description": "Tensors and Dynamic neural networks in Python with strong GPU acceleration.",
    },
    {
        "keywords": ["transformers", "huggingface", "llm library"],
        "target_name": "Hugging Face Transformers",
        "packages": {
            "python": ["transformers", "tokenizers", "accelerate"],
        },
        "description": "State-of-the-art Machine Learning for PyTorch, TensorFlow, and JAX.",
    },
    {
        "keywords": ["image", "images", "pillow", "pil", "image editing"],
        "target_name": "Pillow Image Processing Library",
        "packages": {
            "python": ["pillow"],
            "node": ["sharp"],
        },
        "description": "Python Imaging Library (Fork) adds image processing capabilities to your Python interpreter.",
    },
    {
        "keywords": ["test", "testing", "pytest", "unit tests"],
        "target_name": "Pytest / Testing Framework",
        "packages": {
            "python": ["pytest", "pytest-cov"],
            "node": ["jest"],
        },
        "description": "Mature, full-featured Python testing tool that helps you write better programs.",
    },
]


def resolve_app_key(query: str) -> Optional[str]:
    """Resolves a raw query string to a canonical app key in APP_CATALOG, with typo tolerance."""
    import difflib
    cleaned = query.strip().lower()
    
    # Exact alias match
    if cleaned in APP_ALIASES:
        return APP_ALIASES[cleaned]
    
    # Substring / pattern matching
    for alias, key in APP_ALIASES.items():
        if f" {alias} " in f" {cleaned} " or cleaned.endswith(f" {alias}") or cleaned.startswith(f"{alias} "):
            return key

    # Fuzzy matching for typos (e.g. "whasapp", "whatsap", "watsapp", "dokcer", "chome")
    matches = difflib.get_close_matches(cleaned, APP_ALIASES.keys(), n=1, cutoff=0.72)
    if matches:
        return APP_ALIASES[matches[0]]
        
    return None


def resolve_natural_language_library(query: str, preferred_ecosystem: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Resolves natural language queries for libraries (e.g. 'I need a library to handle Excel files')."""
    cleaned = query.lower()
    
    for item in NL_LIBRARY_MAP:
        for kw in item["keywords"]:
            if kw in cleaned:
                ecosystem = preferred_ecosystem or "python"
                if ecosystem not in item["packages"]:
                    ecosystem = list(item["packages"].keys())[0]
                
                return {
                    "target_name": item["target_name"],
                    "ecosystem": ecosystem,
                    "packages": item["packages"][ecosystem],
                    "description": item["description"],
                }
    return None
