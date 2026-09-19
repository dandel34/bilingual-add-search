"""打包/生成扩展包与旧版单文件插件。

仓库本身就是标准扩展包（根目录 `__init__.py` + `blender_manifest.toml`），
本脚本负责：

1. 依据 `__init__.py` 里的 `bl_info` 生成根目录 `blender_manifest.toml`（提交进仓库）；
2. 生成 `dist/bilingual_add_search-<版本>.zip`：扩展包安装包（zip 内是
   `bilingual_add_search/` 子目录，Blender 4.2+「从磁盘安装」可用，
   旧版 Blender 的插件安装器也接受这种结构）；
3. 生成 `dist/bilingual_add_search.py`：Blender 3.x–4.1 用的旧版单文件插件。

zip 使用固定时间戳，重复打包字节一致，便于 CI 校验提交物与源码同步。
"""

import ast
import io
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "__init__.py"
MANIFEST = ROOT / "blender_manifest.toml"
DIST = ROOT / "dist"
PKG_NAME = "bilingual_add_search"
LEGACY_PY = DIST / f"{PKG_NAME}.py"

# 固定时间戳，保证可重现构建（重复打包字节一致）
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def addon_info():
    """元数据以 __init__.py 的 bl_info 为准，避免两处不同步。"""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "bl_info":
            return ast.literal_eval(node.value)
    raise SystemExit("bl_info not found in %s" % SOURCE)


INFO = addon_info()
VERSION = ".".join(str(part) for part in INFO["version"])

MANIFEST_TEXT = f'''schema_version = "1.0.0"

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

# 扩展包之外还应该带上仓库里的说明/许可证（Blender 会忽略这些文件）
EXTRA_FILES = ("README.md", "CHANGELOG.md", "LICENSE")


def entries():
    """zip 条目: [(zip 内路径, 字节内容), ...]"""
    items = [(f"{PKG_NAME}/__init__.py", SOURCE.read_bytes()),
             (f"{PKG_NAME}/blender_manifest.toml", MANIFEST_TEXT.encode("utf-8"))]
    for name in EXTRA_FILES:
        path = ROOT / name
        if path.exists():
            items.append((f"{PKG_NAME}/{name}", path.read_bytes()))
    return items


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
    DIST.mkdir(parents=True, exist_ok=True)

    MANIFEST.write_text(MANIFEST_TEXT, encoding="utf-8", newline="\n")
    ZIP_PATH.write_bytes(build_zip_bytes())
    LEGACY_PY.write_bytes(SOURCE.read_bytes())

    print("version  : %s" % VERSION)
    print("manifest : %s" % MANIFEST.relative_to(ROOT))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for name in archive.namelist():
            print("  entry  : %s" % name)
    print("zip      : %d bytes -> %s" % (ZIP_PATH.stat().st_size, ZIP_PATH.relative_to(ROOT)))
    print("legacy   : %d bytes -> %s" % (LEGACY_PY.stat().st_size, LEGACY_PY.relative_to(ROOT)))


if __name__ == "__main__":
    main()
