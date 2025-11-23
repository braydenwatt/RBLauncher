#!/usr/bin/env python3
"""Test harness to simulate installing mods and show the install progress dialog.
This avoids real network IO by monkey-patching `install_single_mod` and `install_dependency` with fast fakes.
"""
import sys
import time
import types

from PyQt5.QtWidgets import QApplication

from install_mods_window import install_mods_window


def fake_install_single_mod(self, mod, version_data, mod_data_list, processed_projects):
    """Simulate installing a single mod (runs in worker thread)."""
    # Simulate some work
    time.sleep(0.6)
    mod_entry = {
        "id": version_data.get("id", "fakeid"),
        "project_id": mod.get("project_id", "fakeproj"),
        "title": mod.get("title"),
        "version": version_data.get("version_number", "1.0"),
        "filenames": [f"{mod.get('title').replace(' ', '_')}.jar"],
        "enabled": True,
        "author": mod.get("author", "tester"),
        "description": mod.get("description", "")
    }
    mod_data_list.append(mod_entry)
    processed_projects.add(mod_entry["project_id"])
    return True


def fake_install_dependency(self, dep_project_id, mod_data_list, processed_projects, parent_version_data=None):
    """Simulate installing a dependency."""
    time.sleep(0.2)
    dep_entry = {
        "id": f"dep_{dep_project_id}",
        "project_id": dep_project_id,
        "title": f"Dependency {dep_project_id}",
        "version": "1.0",
        "filenames": [f"{dep_project_id}.jar"],
        "enabled": True,
    }
    mod_data_list.append(dep_entry)
    processed_projects.add(dep_project_id)
    return True


def main():
    app = QApplication(sys.argv)

    # Create window and set up fake data
    window = install_mods_window(theme_colors="dark", instance_name="TestInstance")

    mods = []
    version_map = {}
    for i in range(1, 4):
        mod = {
            "project_id": f"proj{i}",
            "title": f"Fake Mod {i}",
            "author": "Tester",
            "description": "This is a simulated mod for testing.",
            "version": f"v{i}",
        }
        mods.append(mod)
        version_map[f"v{i}"] = {
            "id": f"ver{i}",
            "version_number": f"v{i}",
            "files": [{"filename": f"fake{i}.jar", "primary": True}],
            "dependencies": []
        }

    # Inject fake maps and selection
    window.version_map = version_map
    window.selected_mods = mods

    # Monkey-patch installation helpers to avoid network
    window.install_single_mod = types.MethodType(fake_install_single_mod, window)
    window.install_dependency = types.MethodType(fake_install_dependency, window)

    window.show()

    # Start install flow (will open modal progress dialog)
    window.install_mods()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
