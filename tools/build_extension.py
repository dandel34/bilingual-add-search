"""Build installable artifacts from the single-file addon source.

Outputs (repository-relative):
  dist/bilingual_add_search/__init__.py           - extension package source
  dist/bilingual_add_search/blender_manifest.toml - extension manifest (Blender 4.2+)
  dist/bilingual_add_search-<version>.zip         - zip installable via "Install from Disk"

The zip is written with fixed timestamps so repeated builds are byte-identical;
that lets CI verify the committed zip really matches the current source.
"""

import ast
import io
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bilingual_add_search.py"
DIST = ROOT / "dist"
PKG_NAME = "bilingual_add_search"
PKG = DIST / PKG_NAME

# 固定时间戳，保证可重现构建（重复打包字节一致）
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


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

id = "{PKG_NAME}"
version = "{VERSION}"
name = "Bilingual Add Search"
tagline = "添加菜单与节点菜单：中文、英文关键词都能搜到同一条目"
maintainer = "DSH"
type = "add-on"

blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]

tags = ["User Interface", "Object"]
'''

ZIP_PATH = DIST / f"{PKG_NAME}-{VERSION}.zip"


def entries():
    """扩展包条目: [(zip 内路径, 字节内容), ...]"""
    return [
        (f"{PKG_NAME}/__init__.py", SOURCE.read_bytes()),
        (f"{PKG_NAME}/blender_manifest.toml", MANIFEST.encode("utf-8")),
    ]


def build_zip_bytes():
    """在内存里生成 zip（可重现），打包与校验共用同一实现。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for arcname, data in entries():
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, PKG / "__init__.py")
    (PKG / "blender_manifest.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    ZIP_PATH.write_bytes(build_zip_bytes())

    print("version : %s" % VERSION)
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for name in archive.namelist():
            print("  entry : %s" % name)
    print("bytes   : %d -> %s" % (ZIP_PATH.stat().st_size, ZIP_PATH))


if __name__ == "__main__":
    main()
