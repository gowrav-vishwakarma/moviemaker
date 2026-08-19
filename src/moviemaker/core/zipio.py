"""ZIP import/export for whole projects."""

from __future__ import annotations

import zipfile
from pathlib import Path

from moviemaker.core.project import PROJECT_FILENAME, load_project, save_project, Project


def export_zip(project: Project, dest: Path | None = None) -> Path:
    save_project(project)
    dest = dest or project.export_dir() / f"{project.name.replace(' ', '_')}.zip"
    root = project.dir()
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] == "tmp":
                continue
            zf.write(path, rel)
    return dest


def import_zip(archive: Path, dest_folder: Path) -> Project:
    dest_folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest_folder)
    if not (dest_folder / PROJECT_FILENAME).exists():
        nested = list(dest_folder.glob(f"*/{PROJECT_FILENAME}"))
        if nested:
            dest_folder = nested[0].parent
    return load_project(dest_folder)
