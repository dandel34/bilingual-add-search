"""校验安装包、扩展 manifest 与源码是否同步。

CI 与本地都能跑：

    python tools/build_extension.py
    python tools/check_package.py

检查项：
1. `bilingual_add_search.py` 能编译（语法正确）；
2. 生成的 `blender_manifest.toml` 的 id / version / type / license 与 `bl_info` 一致；
3. 仓库里提交的 `dist/bilingual_add_search-<版本>.zip` 与**当前源码重新打包的结果逐字节一致**
   （打包使用固定时间戳，可重现；不一致说明忘了重新打包并提交）；
4. zip 结构正确：`__init__.py` 必须位于子目录内（放在 zip 根目录时 Blender 会报
   "ZIP packaged incorrectly"），且条目分隔符不能是反斜杠。
"""

import pathlib
import sys
import zipfile

# 控制台编码（Windows GBK）无法编码 ✓/✗ 时不要崩，退化成 '?'
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bilingual_add_search.py"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import build_extension  # noqa: E402  (同目录工具，复用打包实现)

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

REQUIRED_LICENSE = "GPL-3.0-or-later"


def main():
    errors = []
    notes = []

    try:
        compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec")
    except SyntaxError as exc:
        errors.append("插件语法错误: %s" % exc)

    info = build_extension.BL_INFO
    version = build_extension.VERSION
    print("插件版本: %s（bl_info）" % version)

    # --- manifest 内容
    manifest_text = build_extension.MANIFEST
    if tomllib is None:
        notes.append("Python < 3.11，跳过 manifest 解析（CI 使用 3.12）")
    else:
        data = tomllib.loads(manifest_text)
        print("manifest: id=%s version=%s license=%s"
              % (data.get("id"), data.get("version"), data.get("license")))
        if data.get("id") != build_extension.PKG_NAME:
            errors.append("manifest id = %r，期望 %r"
                          % (data.get("id"), build_extension.PKG_NAME))
        if data.get("version") != version:
            errors.append("manifest version = %r，但 bl_info 是 %r"
                          % (data.get("version"), version))
        if data.get("type") != "add-on":
            errors.append("manifest type = %r，期望 'add-on'" % data.get("type"))
        licenses = data.get("license") or []
        if not any(REQUIRED_LICENSE in item for item in licenses):
            errors.append("manifest license = %r，缺少 %s" % (licenses, REQUIRED_LICENSE))

    # --- zip 结构
    zip_path = build_extension.ZIP_PATH
    if not zip_path.exists():
        errors.append("缺少安装包 %s（请运行 tools/build_extension.py）" % zip_path.name)
    else:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            if "__init__.py" in names:
                errors.append("zip 根目录下有 __init__.py，Blender 会拒绝安装")
            for name in names:
                if "\\" in name:
                    errors.append("zip 条目使用了反斜杠: %s" % name)
            for arcname, _data in build_extension.entries():
                if arcname not in names:
                    errors.append("zip 里缺少 %s" % arcname)
        notes.append("安装包: %s（%d 个条目，%d 字节）"
                     % (zip_path.name, len(names), zip_path.stat().st_size))

        # --- 与当前源码重新打包的结果逐字节比对
        expected = build_extension.build_zip_bytes()
        if zip_path.read_bytes() != expected:
            errors.append("提交的 %s 与当前源码不一致，请重新运行 tools/build_extension.py 并提交"
                          % zip_path.name)
        else:
            notes.append("安装包与当前源码一致（可重现构建）")

    for note in notes:
        print("· %s" % note)
    if errors:
        print("\n发现 %d 个问题:" % len(errors))
        for error in errors:
            print("  [x] %s" % error)
        return 1
    print("\n全部检查通过 [OK]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
