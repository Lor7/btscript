#!/usr/bin/env python3
"""
Installer for the BTScript VS Code Extension.
Installs the full 'vscode-btscript' extension directly into your active
VS Code / VSCodium / Cursor extensions directory so that '.tree' files
receive rich syntax highlighting, keyword completion, and bracket matching.
"""

import os
import shutil
import sys
from pathlib import Path


def install_extension() -> bool:
    home = Path.home()
    possible_targets = [
        home / ".vscode" / "extensions" / "vscode-btscript",
        home / ".vscode-oss" / "extensions" / "vscode-btscript",
        home / ".cursor" / "extensions" / "vscode-btscript",
    ]

    # Source directory locations (local repo or packaged install)
    repo_root = Path(__file__).resolve().parent.parent
    candidate_sources = [
        repo_root / "editors" / "vscode-btscript",
        repo_root / "btscript" / "editors" / "vscode-btscript",
    ]

    source_dir = None
    for src in candidate_sources:
        if src.exists() and (src / "package.json").exists():
            source_dir = src
            break

    if not source_dir:
        print("[ERROR] Could not find 'vscode-btscript' extension source directory.")
        return False

    installed_any = False
    for target in possible_targets:
        parent = target.parent
        # Install into existing editor folders, or create ~/.vscode/extensions if none exist
        if parent.exists() or (target == possible_targets[0]):
            parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_dir, target)
            print(f"[SUCCESS] Installed BTScript VS Code extension into: {target}")
            installed_any = True

    if installed_any:
        print("\nBTScript Language Support Extension is now installed!")
        print("To activate syntax highlighting in your editor:")
        print("  1. Open or restart VS Code / VSCodium / Cursor")
        print("  2. Open any '.tree' file to see syntax highlighting")
        print("  3. (Optional) In VS Code, press Ctrl+Shift+P -> 'Developer: Reload Window'")
    return installed_any


if __name__ == "__main__":
    success = install_extension()
    sys.exit(0 if success else 1)
