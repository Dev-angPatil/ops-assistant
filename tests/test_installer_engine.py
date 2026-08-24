"""
Unit and integration tests for the AI-Powered Software, Dependency, and Resource Installer.
"""

import os
import tempfile
import pytest
from pathlib import Path

from ops_assistant.installer.engine import PackageInstallerEngine
from ops_assistant.installer.models import (
    InstallPhase,
    InstallPlan,
    InstallProgressEvent,
    InstallResult,
    InstallSource,
    InstallStep,
    InstallTargetType,
)
from ops_assistant.installer.knowledge_base import (
    APP_CATALOG,
    APP_ALIASES,
    resolve_app_key,
    resolve_natural_language_library,
)
from ops_assistant.installer.project_detector import ProjectDependencyDetector
from ops_assistant.installer.file_installer import LocalFileInstaller
from ops_assistant.installer.sources import SourceResolver
from ops_assistant.installer.verifier import InstallationVerifier
from ops_assistant.explainer.xai import ErrorExplainer
from ops_assistant.agent.core import ReActAgent
from ops_assistant.nlp.intent_router import IntentRouter, IntentType


class TestInstallerKnowledgeBase:
    def test_app_key_resolution(self):
        assert resolve_app_key("vscode") == "vscode"
        assert resolve_app_key("vs code") == "vscode"
        assert resolve_app_key("visual studio code") == "vscode"
        assert resolve_app_key("whatsapp") == "whatsapp"
        assert resolve_app_key("google chrome") == "chrome"
        assert resolve_app_key("docker") == "docker"
        assert resolve_app_key("java 21") == "java_21"
        assert resolve_app_key("android studio") == "android_studio"
        assert resolve_app_key("obs studio") == "obs_studio"
        assert resolve_app_key("mysql") == "mysql"
        assert resolve_app_key("postgres") == "postgresql"

    def test_natural_language_library_resolution(self):
        res = resolve_natural_language_library("I need a library to handle Excel files.")
        assert res is not None
        assert "openpyxl" in res["packages"]
        assert "pandas" in res["packages"]

        res_pdf = resolve_natural_language_library("I want to parse and read pdf files")
        assert res_pdf is not None
        assert "pypdf" in res_pdf["packages"]

        res_http = resolve_natural_language_library("I need an http rest client")
        assert res_http is not None
        assert "requests" in res_http["packages"]


class TestDistroAdaptiveResolution:
    def test_whatsapp_resolution_on_arch(self):
        engine = PackageInstallerEngine(distro_override="arch")
        plan = engine.resolve_plan("i have to install whatsapp", distro_override="arch")
        assert plan is not None
        assert "WhatsApp" in plan.target_name
        assert plan.source in (InstallSource.AUR, InstallSource.YAY, InstallSource.PARU, InstallSource.FLATPAK)
        assert "whatsapp" in plan.primary_command.lower()

    def test_whatsapp_resolution_on_ubuntu(self):
        engine = PackageInstallerEngine(distro_override="debian")
        plan = engine.resolve_plan("install whatsapp", distro_override="debian")
        assert plan is not None
        assert "WhatsApp" in plan.target_name
        assert plan.source in (InstallSource.FLATPAK, InstallSource.SNAP, InstallSource.APT)

    def test_vscode_resolution_on_arch_and_debian(self):
        engine_arch = PackageInstallerEngine(distro_override="arch")
        plan_arch = engine_arch.resolve_plan("Install VS Code", distro_override="arch")
        assert "code" in plan_arch.primary_command

        engine_deb = PackageInstallerEngine(distro_override="debian")
        plan_deb = engine_deb.resolve_plan("Install VS Code", distro_override="debian")
        assert "code" in plan_deb.primary_command or "visualstudio" in plan_deb.primary_command

    def test_excel_library_query(self):
        engine = PackageInstallerEngine(distro_override="arch")
        plan = engine.resolve_plan("I need a library to handle Excel files.")
        assert plan.target_type == InstallTargetType.LANGUAGE_LIBRARY
        assert "openpyxl" in plan.primary_command
        assert "pandas" in plan.primary_command

    def test_docker_and_compose(self):
        engine = PackageInstallerEngine(distro_override="arch")
        plan = engine.resolve_plan("install docker", distro_override="arch")
        assert "docker" in plan.primary_command


class TestProjectDependencyDetection:
    def test_python_requirements_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("fastapi\nuvicorn\npydantic\n")

            plan = ProjectDependencyDetector.detect_and_plan(root_dir=tmpdir, distro_family="arch")
            assert plan is not None
            assert plan.target_type == InstallTargetType.PROJECT_DEPENDENCIES
            assert any("requirements.txt" in s.command for s in plan.steps)

    def test_node_package_json_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_json = Path(tmpdir) / "package.json"
            pkg_json.write_text('{"name": "my-app", "dependencies": {"express": "^4.18.2"}}')

            plan = ProjectDependencyDetector.detect_and_plan(root_dir=tmpdir, distro_family="arch")
            assert plan is not None
            assert plan.target_type == InstallTargetType.PROJECT_DEPENDENCIES
            assert plan.source == InstallSource.NPM
            assert "npm install" in plan.primary_command

    def test_rust_cargo_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo_toml = Path(tmpdir) / "Cargo.toml"
            cargo_toml.write_text('[package]\nname = "my_crate"\nversion = "0.1.0"\n')

            plan = ProjectDependencyDetector.detect_and_plan(root_dir=tmpdir, distro_family="arch")
            assert plan is not None
            assert plan.source == InstallSource.CARGO
            assert "cargo" in plan.primary_command

    def test_go_mod_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            go_mod = Path(tmpdir) / "go.mod"
            go_mod.write_text("module example.com/myapp\n\ngo 1.22\n")

            plan = ProjectDependencyDetector.detect_and_plan(root_dir=tmpdir, distro_family="arch")
            assert plan is not None
            assert plan.source == InstallSource.GO
            assert "go mod" in plan.primary_command

    def test_java_maven_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pom_xml = Path(tmpdir) / "pom.xml"
            pom_xml.write_text("<project><modelVersion>4.0.0</modelVersion></project>")

            plan = ProjectDependencyDetector.detect_and_plan(root_dir=tmpdir, distro_family="arch")
            assert plan is not None
            assert plan.source == InstallSource.MAVEN
            assert "mvn" in plan.primary_command


class TestLocalFileInstaller:
    def test_deb_file_planning(self):
        plan = LocalFileInstaller.plan_file_install("/tmp/discord.deb", distro_family="debian")
        assert plan is not None
        assert plan.source == InstallSource.DEB_FILE
        assert "apt install" in plan.primary_command or "dpkg -i" in plan.primary_command

    def test_appimage_planning(self):
        plan = LocalFileInstaller.plan_file_install("/home/user/Downloads/cursor.AppImage", distro_family="arch")
        assert plan is not None
        assert plan.source == InstallSource.APPIMAGE
        assert "chmod +x" in plan.primary_command
        assert ".local/bin" in plan.primary_command

    def test_rpm_planning(self):
        plan = LocalFileInstaller.plan_file_install("/tmp/package.rpm", distro_family="rhel")
        assert plan is not None
        assert plan.source == InstallSource.RPM_FILE
        assert "dnf install" in plan.primary_command or "rpm -Uvh" in plan.primary_command


class TestLockConflictClassificationFix:
    def test_pacman_lock_diagnosed_as_lock_conflict(self):
        pacman_err = """
error: failed to init transaction (unable to lock database)
error: could not lock database: File exists
  if you're sure a package manager is not already
  running, you can remove /var/lib/pacman/db.lck
"""
        diag = ErrorExplainer.explain(
            command="sudo pacman -S whatsapp",
            returncode=1,
            stderr=pacman_err
        )
        assert diag["error_class"] == "LOCK_CONFLICT"
        assert "db.lck" in diag["diagnosis"] or "lock" in diag["diagnosis"].lower()
        assert "rm /var/lib/pacman/db.lck" in diag["recommendation"]

    def test_generic_file_already_exists(self):
        generic_err = "mkdir: cannot create directory 'test': File exists"
        diag = ErrorExplainer.explain(
            command="mkdir test",
            returncode=1,
            stderr=generic_err
        )
        assert diag["error_class"] == "FILE_ALREADY_EXISTS"


class TestAgentAndIntentRouterIntegration:
    def test_intent_router_classifies_install_queries(self):
        router = IntentRouter()

        i1 = router.route("i have to install whatsapp")
        assert i1.type == IntentType.PACKAGE_INSTALL

        i2 = router.route("install VS Code")
        assert i2.type == IntentType.PACKAGE_INSTALL

        i3 = router.route("I need a library to handle Excel files.")
        assert i3.type == IntentType.PACKAGE_INSTALL

        i4 = router.route("install this project's dependencies")
        assert i4.type == IntentType.PACKAGE_INSTALL

    def test_react_agent_interprets_install_command(self):
        agent = ReActAgent()
        interp = agent.interpret_command("install vs code")
        assert interp is not None
        assert len(interp["plan_steps"]) > 0
        assert "code" in interp["plan_steps"][0]["command"].lower()

    def test_engine_dry_run_execution(self):
        engine = PackageInstallerEngine(distro_override="arch")
        plan = engine.resolve_plan("install git", distro_override="arch")
        result = engine.execute_plan(plan, dry_run=True)
        assert result.success is True
        assert result.verified is True
        assert "[DRY RUN]" in result.stdout


class TestGUIRestEndpoints:
    @classmethod
    def setup_class(cls):
        import threading
        import time
        from ops_assistant.gui.server import start_gui_server
        cls.agent = ReActAgent()
        cls.server, cls.url = start_gui_server(
            host="127.0.0.1",
            port=9933,
            open_browser=False,
            agent=cls.agent
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def teardown_class(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, endpoint):
        import urllib.request
        import json
        req = urllib.request.Request(f"{self.url}{endpoint}", headers={"Connection": "close"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, endpoint, data):
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{self.url}{endpoint}",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connection": "close"}
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_installer_sources_endpoint(self):
        status, data = self._get("/api/installer/sources")
        assert status == 200
        assert "distro_name" in data
        assert "has_pacman" in data or "has_apt" in data

    def test_installer_catalog_endpoint(self):
        status, data = self._get("/api/installer/catalog")
        assert status == 200
        assert "catalog" in data
        assert data["count"] > 10
        assert "vscode" in data["catalog"]

    def test_installer_project_detect_endpoint(self):
        status, data = self._get("/api/installer/project-detect")
        assert status == 200
        assert "detected" in data
        if data["detected"]:
            assert "plan" in data

    def test_installer_resolve_endpoint(self):
        status, data = self._post("/api/installer/resolve", {"query": "install VS Code"})
        assert status == 200
        assert data["success"] is True
        assert "plan" in data
        assert "code" in data["plan"]["primary_command"]

    def test_installer_cancel_endpoint(self):
        status, data = self._post("/api/installer/cancel", {"session_id": "dummy-123"})
        assert status == 200
        assert data["success"] is True
