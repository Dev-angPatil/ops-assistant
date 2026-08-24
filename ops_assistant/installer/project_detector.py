"""
Project dependency detector and builder for Python, Node.js, Rust, Go, Java, PHP, .NET, Flutter, and Ruby.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ops_assistant.installer.models import InstallPlan, InstallSource, InstallStep, InstallTargetType
from ops_assistant.models import SafetyLevel


class ProjectDependencyDetector:
    """
    Introspects a project repository directory to determine the tech stack
    and generate the exact dependency installation steps.
    """

    @classmethod
    def detect_and_plan(cls, root_dir: Optional[str] = None, distro_family: str = "arch") -> Optional[InstallPlan]:
        path = Path(root_dir).resolve() if root_dir else Path.cwd()

        if not path.is_dir():
            return None

        # 1. Python Project
        py_plan = cls._detect_python(path, distro_family)
        if py_plan:
            return py_plan

        # 2. Node.js / JavaScript / TypeScript Project
        node_plan = cls._detect_node(path, distro_family)
        if node_plan:
            return node_plan

        # 3. Rust Project
        rust_plan = cls._detect_rust(path, distro_family)
        if rust_plan:
            return rust_plan

        # 4. Go Project
        go_plan = cls._detect_go(path, distro_family)
        if go_plan:
            return go_plan

        # 5. Java (Maven / Gradle) Project
        java_plan = cls._detect_java(path, distro_family)
        if java_plan:
            return java_plan

        # 6. Flutter / Dart Project
        flutter_plan = cls._detect_flutter(path, distro_family)
        if flutter_plan:
            return flutter_plan

        # 7. PHP (Composer) Project
        php_plan = cls._detect_php(path, distro_family)
        if php_plan:
            return php_plan

        # 8. .NET Project
        dotnet_plan = cls._detect_dotnet(path, distro_family)
        if dotnet_plan:
            return dotnet_plan

        # 9. Ruby (Bundler) Project
        ruby_plan = cls._detect_ruby(path, distro_family)
        if ruby_plan:
            return ruby_plan

        return None

    @classmethod
    def _detect_python(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        req_txt = path / "requirements.txt"
        pyproject = path / "pyproject.toml"
        pipfile = path / "Pipfile"
        setup_py = path / "setup.py"
        poetry_lock = path / "poetry.lock"
        uv_lock = path / "uv.lock"

        if not (req_txt.exists() or pyproject.exists() or pipfile.exists() or setup_py.exists()):
            return None

        # Check for virtual environment
        venv_path = None
        for candidate in [".venv", "venv", "env"]:
            v_dir = path / candidate
            if v_dir.is_dir() and ((v_dir / "bin" / "pip").exists() or (v_dir / "bin" / "python").exists()):
                venv_path = v_dir
                break

        steps: List[InstallStep] = []
        source = InstallSource.PIP
        source_label = "Python (pip)"
        py_bin = f"{venv_path}/bin/python3" if venv_path else "python3"
        pip_bin = f"{venv_path}/bin/pip" if venv_path else "pip"

        # If no virtual environment, plan virtualenv creation
        if not venv_path:
            steps.append(InstallStep(
                command="python3 -m venv .venv",
                description="Creates an isolated Python virtual environment (.venv) to prevent system package conflicts.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.10,
                requires_sudo=False,
                rollback_command="rm -rf .venv",
                working_dir=str(path)
            ))
            pip_bin = ".venv/bin/pip"
            py_bin = ".venv/bin/python3"

        # Check for UV or Poetry or Pip
        if uv_lock.exists() and shutil.which("uv"):
            source = InstallSource.UV
            source_label = "Python (uv sync)"
            steps.append(InstallStep(
                command="uv sync",
                description="Fast-syncs Python project virtualenv and lockfile dependencies via uv.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            ))
        elif poetry_lock.exists() and shutil.which("poetry"):
            source = InstallSource.POETRY
            source_label = "Python (Poetry)"
            steps.append(InstallStep(
                command="poetry install",
                description="Installs all locked dependencies using Poetry package manager.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            ))
        elif pipfile.exists() and shutil.which("pipenv"):
            source = InstallSource.PIPENV
            source_label = "Python (Pipenv)"
            steps.append(InstallStep(
                command="pipenv install",
                description="Installs project dependencies from Pipfile into pipenv virtualenv.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            ))
        elif req_txt.exists():
            steps.append(InstallStep(
                command=f"{pip_bin} install -r requirements.txt",
                description="Installs Python packages listed in requirements.txt into the environment.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                working_dir=str(path)
            ))
        elif pyproject.exists():
            steps.append(InstallStep(
                command=f"{pip_bin} install -e .",
                description="Installs the package in editable mode with dependencies from pyproject.toml.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                working_dir=str(path)
            ))
        elif setup_py.exists():
            steps.append(InstallStep(
                command=f"{pip_bin} install -e .",
                description="Installs the package in editable mode with dependencies from setup.py.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                working_dir=str(path)
            ))

        return InstallPlan(
            query="install python project dependencies",
            target_name=f"Python Dependencies ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=source,
            source_label=source_label,
            distro_family=distro_family,
            steps=steps,
            explanation=f"Detected Python project in '{path.name}'. Installs all required packages in isolated virtual environment.",
            verification_method="custom",
            verification_target=f"{py_bin} -c 'import sys; print(\"Python project environment ready\")'",
            launch_instructions="Activate virtualenv with 'source .venv/bin/activate'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.25
        )

    @classmethod
    def _detect_node(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        pkg_json = path / "package.json"
        if not pkg_json.exists():
            return None

        pnpm_lock = path / "pnpm-lock.yaml"
        yarn_lock = path / "yarn.lock"
        bun_lock = path / "bun.lockb"

        if pnpm_lock.exists() and shutil.which("pnpm"):
            cmd = "pnpm install"
            src = InstallSource.PNPM
            label = "Node.js (pnpm)"
        elif yarn_lock.exists() and shutil.which("yarn"):
            cmd = "yarn install"
            src = InstallSource.YARN
            label = "Node.js (yarn)"
        elif bun_lock.exists() and shutil.which("bun"):
            cmd = "bun install"
            src = InstallSource.BUN
            label = "JavaScript (bun)"
        else:
            cmd = "npm install"
            src = InstallSource.NPM
            label = "Node.js (npm)"

        return InstallPlan(
            query="install node project dependencies",
            target_name=f"Node.js Dependencies ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=src,
            source_label=label,
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description=f"Installs all npm dependencies defined in package.json using {label}.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                rollback_command="rm -rf node_modules",
                working_dir=str(path)
            )],
            explanation=f"Detected Node.js project in '{path.name}'. Installs packages into 'node_modules'.",
            verification_method="custom",
            verification_target=f"[ -d '{path}/node_modules' ]",
            launch_instructions="Run scripts via 'npm start' or 'npm run dev'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.25
        )

    @classmethod
    def _detect_rust(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        cargo_toml = path / "Cargo.toml"
        if not cargo_toml.exists():
            return None

        return InstallPlan(
            query="install rust project dependencies",
            target_name=f"Rust Crates ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.CARGO,
            source_label="Rust (Cargo)",
            distro_family=distro_family,
            steps=[InstallStep(
                command="cargo check",
                description="Fetches, builds, and verifies all crate dependencies specified in Cargo.toml.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            )],
            explanation=f"Detected Rust project in '{path.name}'. Fetches and compiles crate dependencies.",
            verification_method="custom",
            verification_target="cargo --version",
            launch_instructions="Run project with 'cargo run' or build with 'cargo build --release'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.20
        )

    @classmethod
    def _detect_go(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        go_mod = path / "go.mod"
        if not go_mod.exists():
            return None

        return InstallPlan(
            query="install go project dependencies",
            target_name=f"Go Modules ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.GO,
            source_label="Go Modules",
            distro_family=distro_family,
            steps=[InstallStep(
                command="go mod download && go mod tidy",
                description="Downloads all Go module dependencies listed in go.mod and verifies checksums in go.sum.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            )],
            explanation=f"Detected Go project in '{path.name}'. Downloads and verifies Go modules.",
            verification_method="custom",
            verification_target="go version",
            launch_instructions="Run with 'go run .' or build binary with 'go build .'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.20
        )

    @classmethod
    def _detect_java(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        pom_xml = path / "pom.xml"
        build_gradle = path / "build.gradle"
        build_gradle_kts = path / "build.gradle.kts"

        if pom_xml.exists():
            mvn_cmd = "./mvnw dependency:resolve" if (path / "mvnw").exists() else "mvn dependency:resolve"
            return InstallPlan(
                query="install java maven dependencies",
                target_name=f"Java Maven Dependencies ({path.name})",
                target_type=InstallTargetType.PROJECT_DEPENDENCIES,
                source=InstallSource.MAVEN,
                source_label="Java (Maven)",
                distro_family=distro_family,
                steps=[InstallStep(
                    command=mvn_cmd,
                    description="Resolves and downloads all Maven dependencies declared in pom.xml.",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.20,
                    requires_sudo=False,
                    working_dir=str(path)
                )],
                explanation=f"Detected Maven project in '{path.name}'. Downloads jar artifacts to local repository.",
                verification_method="custom",
                verification_target="mvn -v || ./mvnw -v",
                launch_instructions="Build project with 'mvn package' or 'mvn spring-boot:run'",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20
            )

        if build_gradle.exists() or build_gradle_kts.exists():
            gradle_cmd = "./gradlew build --refresh-dependencies" if (path / "gradlew").exists() else "gradle build"
            return InstallPlan(
                query="install java gradle dependencies",
                target_name=f"Java Gradle Dependencies ({path.name})",
                target_type=InstallTargetType.PROJECT_DEPENDENCIES,
                source=InstallSource.GRADLE,
                source_label="Java (Gradle)",
                distro_family=distro_family,
                steps=[InstallStep(
                    command=gradle_cmd,
                    description="Builds project and caches all Gradle dependencies from build.gradle.",
                    safety_level=SafetyLevel.MODIFYING,
                    risk_score=0.20,
                    requires_sudo=False,
                    working_dir=str(path)
                )],
                explanation=f"Detected Gradle project in '{path.name}'. Resolves dependencies and builds artifacts.",
                verification_method="custom",
                verification_target="gradle -v || ./gradlew -v",
                launch_instructions="Run project with './gradlew run' or 'gradle run'",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20
            )

        return None

    @classmethod
    def _detect_flutter(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        pubspec = path / "pubspec.yaml"
        if not pubspec.exists():
            return None

        cmd = "flutter pub get" if shutil.which("flutter") else "dart pub get"
        return InstallPlan(
            query="install flutter / dart dependencies",
            target_name=f"Flutter / Dart Packages ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.FLUTTER,
            source_label="Flutter / Dart Pub",
            distro_family=distro_family,
            steps=[InstallStep(
                command=cmd,
                description="Fetches and caches all packages listed in pubspec.yaml.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            )],
            explanation=f"Detected Flutter/Dart project in '{path.name}'. Fetches packages via pub.",
            verification_method="custom",
            verification_target="flutter --version || dart --version",
            launch_instructions="Launch app with 'flutter run'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.20
        )

    @classmethod
    def _detect_php(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        composer_json = path / "composer.json"
        if not composer_json.exists():
            return None

        return InstallPlan(
            query="install php composer dependencies",
            target_name=f"PHP Composer Packages ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.COMPOSER,
            source_label="PHP (Composer)",
            distro_family=distro_family,
            steps=[InstallStep(
                command="composer install",
                description="Installs all PHP packages defined in composer.json into vendor/.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                rollback_command="rm -rf vendor",
                working_dir=str(path)
            )],
            explanation=f"Detected PHP project in '{path.name}'. Installs packages into vendor directory.",
            verification_method="custom",
            verification_target="[ -d 'vendor' ]",
            launch_instructions="Include vendor/autoload.php in your application",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.25
        )

    @classmethod
    def _detect_dotnet(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        csproj_files = list(path.glob("*.csproj")) or list(path.glob("*.sln"))
        if not csproj_files:
            return None

        return InstallPlan(
            query="install .net dependencies",
            target_name=f".NET Project Packages ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.DOTNET,
            source_label=".NET CLI (dotnet restore)",
            distro_family=distro_family,
            steps=[InstallStep(
                command="dotnet restore",
                description="Restores the dependencies and project-specific tools specified in the project file.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.20,
                requires_sudo=False,
                working_dir=str(path)
            )],
            explanation=f"Detected .NET project in '{path.name}'. Restores NuGet dependencies.",
            verification_method="custom",
            verification_target="dotnet --version",
            launch_instructions="Run project with 'dotnet run' or build with 'dotnet build'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.20
        )

    @classmethod
    def _detect_ruby(cls, path: Path, distro_family: str) -> Optional[InstallPlan]:
        gemfile = path / "Gemfile"
        if not gemfile.exists():
            return None

        return InstallPlan(
            query="install ruby bundler dependencies",
            target_name=f"Ruby Gems ({path.name})",
            target_type=InstallTargetType.PROJECT_DEPENDENCIES,
            source=InstallSource.GEM,
            source_label="Ruby (Bundler)",
            distro_family=distro_family,
            steps=[InstallStep(
                command="bundle install",
                description="Installs the gems specified in your Gemfile.",
                safety_level=SafetyLevel.MODIFYING,
                risk_score=0.25,
                requires_sudo=False,
                working_dir=str(path)
            )],
            explanation=f"Detected Ruby project in '{path.name}'. Installs gems specified in Gemfile.",
            verification_method="custom",
            verification_target="bundle -v",
            launch_instructions="Run with 'bundle exec rails server' or 'ruby app.rb'",
            safety_level=SafetyLevel.MODIFYING,
            risk_score=0.25
        )
