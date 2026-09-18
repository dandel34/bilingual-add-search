"""Build installable artifacts from the single-file addon source.

Outputs (workspace-relative):
  dist/bilingual_add_search/__init__.py          - extension package source
  dist/bilingual_add_search/blender_manifest.toml- extension manifest (Blender 4.2+)
  dist/bilingual_add_search-1.0.0.zip            - zip installable via "Install from Disk"
"""

import ast
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bilingual_add_search.py"
DIST = ROOT / "dist"
PKG = DIST / "bilingual_add_search"


def addon_version():
    """版本号以 bilingual_add_search.py 的 bl_info 为准，避免两处不同步。"""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "bl_info":
            info = ast.literal_eval(node.value)
            return ".".join(str(part) for part in info["version"]), info
    raise SystemExit("bl_info not found in %s" % SOURCE)


VERSION, BL_INFO = addon_version()

MANIFEST = f'''schema_version = "1.0.0"

id = "bilingual_add_search"
version = "{VERSION}"
name = "Bilingual Add Search"
tagline = "添加菜单与节点菜单：中文、英文关键词都能搜到同一条目"
maintainer = "DSH"
type = "add-on"

blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]

tags = ["User Interface", "Object"]
'''


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, PKG / "__init__.py")
    (PKG / "blender_manifest.toml").write_text(MANIFEST, encoding="utf-8")

    zip_path = DIST / f"bilingual_add_search-{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PKG.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(DIST).as_posix())

    with zipfile.ZipFile(zip_path) as zf:
        print("zip entries:")
        for name in zf.namelist():
            print("  ", name)
    print("bytes:", zip_path.stat().st_size, "->", zip_path)


if __name__ == "__main__":
    main()
