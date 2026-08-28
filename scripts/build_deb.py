#!/usr/bin/env python3
"""Build Debian (.deb) package for CivilQntify offline using dpkg-deb.

Usage:
    python scripts/build_deb.py [VERSION]

Default version is 1.0.6 if not provided.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_VERSION = "1.0.6"


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VERSION
    dpkg_deb = shutil.which("dpkg-deb")
    if not dpkg_deb:
        print("error: dpkg-deb not found. Please install dpkg (e.g. sudo apt install dpkg).", file=sys.stderr)
        return 1

    print(f"==> Building CivilQntify v{version} Debian package (.deb)...")

    stage_dir = ROOT / "build" / "deb_stage"
    dist_dir = ROOT / "dist"
    deb_name = f"civilqntify_{version}_amd64.deb"
    output_deb = dist_dir / deb_name

    # 1. Clean previous staging
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 2. Create directory structure
    app_lib_dir = stage_dir / "usr" / "lib" / "civilqntify"
    bin_dir = stage_dir / "usr" / "bin"
    apps_dir = stage_dir / "usr" / "share" / "applications"
    icons_dir = stage_dir / "usr" / "share" / "icons"
    debian_dir = stage_dir / "DEBIAN"

    for d in (app_lib_dir, bin_dir, apps_dir, icons_dir, debian_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 3. Copy application files to /usr/lib/civilqntify/
    print("  -> Copying application packages and modules...")
    for pkg in ("app", "concrete_mix", "material_quantify", "history"):
        src_pkg = ROOT / pkg
        dst_pkg = app_lib_dir / pkg
        if src_pkg.is_dir():
            shutil.copytree(
                src_pkg,
                dst_pkg,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", "*.swp"),
            )

    for single_file in ("main.py", "main_cli.py", "AGENTS.md", "README.md", "RELEASE_NOTES.md"):
        src_file = ROOT / single_file
        if src_file.is_file():
            shutil.copy2(src_file, app_lib_dir / single_file)

    # 4. Compile Python bytecode for fast execution
    print("  -> Compiling bytecode...")
    subprocess.run([sys.executable, "-m", "compileall", "-q", str(app_lib_dir)], check=True)

    # 5. Copy Linux icons
    icons_src = ROOT / "packaging" / "linux-icons" / "hicolor"
    if icons_src.is_dir():
        shutil.copytree(icons_src, icons_dir / "hicolor", dirs_exist_ok=True)

    # 6. Create /usr/bin/civilqntify wrapper script
    launcher_file = bin_dir / "civilqntify"
    launcher_script = (
        "#!/bin/sh\n"
        "# Launcher for CivilQntify desktop application\n"
        "exec /usr/bin/python3 /usr/lib/civilqntify/main.py \"$@\"\n"
    )
    launcher_file.write_text(launcher_script, encoding="utf-8")
    launcher_file.chmod(0o755)

    # 7. Create desktop entry file
    desktop_file = apps_dir / "civilqntify.desktop"
    desktop_content = (
        "[Desktop Entry]\n"
        "Name=CivilQntify\n"
        "Comment=Concrete Mix Design & Structural Material Quantification Desktop App\n"
        "Exec=/usr/bin/civilqntify\n"
        "Icon=civilqntify\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Engineering;Science;Utility;Education;\n"
        "Keywords=Concrete;Mix;Design;Structural;Quantification;PSD;IS10262;ACI211;DOE;BRE331;\n"
    )
    desktop_file.write_text(desktop_content, encoding="utf-8")
    desktop_file.chmod(0o644)

    # 8. Create DEBIAN/control file
    control_file = debian_dir / "control"
    control_content = (
        "Package: civilqntify\n"
        f"Version: {version}\n"
        "Section: science\n"
        "Priority: optional\n"
        "Architecture: amd64\n"
        "Depends: python3 (>= 3.9), python3-pyqt6, python3-matplotlib, python3-numpy, python3-pil, python3-requests\n"
        "Maintainer: CivilQntify Team <netwandererdotcom@gmail.com>\n"
        "Homepage: https://github.com/sthashixi-netwanderer/civilqntify\n"
        "Description: CivilQntify - Concrete Mix Design & Material Quantification\n"
        " CivilQntify is an engineering desktop application for concrete mix\n"
        " proportioning (IS 10262:2019, ACI PRC-211.1-22, BRE 331:1997 / DOE),\n"
        " aggregate Particle Size Distribution (PSD) sieve analysis, and\n"
        " structural material quantification and costing.\n"
    )
    control_file.write_text(control_content, encoding="utf-8")

    # 9. Build Debian package using dpkg-deb
    print("  -> Building .deb package archive...")
    cmd = [
        dpkg_deb,
        "--build",
        "--root-owner-group",
        str(stage_dir),
        str(output_deb),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"error: dpkg-deb build failed:\n{res.stderr}", file=sys.stderr)
        return res.returncode

    file_size_mb = output_deb.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Package built successfully!")
    print(f"  File: {output_deb}")
    print(f"  Size: {file_size_mb:.2f} MB")
    print(f"  Install with: sudo dpkg -i {output_deb.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
