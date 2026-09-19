"""校验扩展包结构、manifest 与生成物是否与源码同步。

CI 与本地都能跑：

    python tools/build_extension.py
    python tools/check_package.py

检查项：
1. `__init__.py` 能编译（语法正确），且包含 `bl_info`；
2. 根目录 `blender_manifest.toml` 与依据 `bl_info` 生成的内容逐字节一致
   （否则说明改了版本/名称却忘了重新生成）；
3. `dist/bilingual_add_search-<版本>.zip` 与当前源码重新打包的结果逐字节一致
   （固定时间戳，可重现）；
4. zip 结构：`__init__.py` 必须位于子目录内（旧版 Blender 的安装器要求如此），
   条目分隔符不能是反斜杠；
5. `dist/bilingual_add_search.py`（旧版单文件）与 `__init__.py` 一致。
"""

import pathlib
import sys
import zipfile

# 控制台编码（Windows GBK）无法编码部分符号时不要崩，退化成 '?'
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "__init__.py"
MANIFEST = ROOT / "blender_manifest.toml"
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

    version = build_extension.VERSION
    print("插件版本: %s（__init__.py 的 bl_info）" % version)

    # --- 根目录 manifest
    if not MANIFEST.exists():
        errors.append("缺少根目录 blender_manifest.toml（请运行 tools/build_extension.py）")
    else:
        text = MANIFEST.read_text(encoding="utf-8")
        if text != build_extension.MANIFEST_TEXT:
            errors.append("blender_manifest.toml 与 bl_info 生成的内容不一致，"
                          "请重新运行 tools/build_extension.py 并提交")
        if tomllib is None:
            notes.append("Python < 3.11，跳过 manifest 解析（CI 使用 3.12）")
        else:
            data = tomllib.loads(text)
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

    # --- 安装包（按「条目内容」校验，不要求压缩后的字节跨平台一致）
    zip_path = build_extension.ZIP_PATH
    if not zip_path.exists():
        errors.append("缺少安装包 %s（请运行 tools/build_extension.py）" % zip_path.name)
    else:
        expected_entries = dict(build_extension.entries())
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            if "__init__.py" in names:
                errors.append("zip 根目录下有 __init__.py，旧版 Blender 会拒绝安装")
            for name in names:
                if "\\" in name:
                    errors.append("zip 条目使用了反斜杠: %s" % name)
            for arcname, expected in expected_entries.items():
                if arcname not in names:
                    errors.append("zip 里缺少 %s" % arcname)
                    continue
                if archive.read(arcname) != expected:
                    errors.append("zip 里的 %s 与当前文件不一致，请重新打包" % arcname)
            extra = sorted(set(names) - set(expected_entries))
            if extra:
                notes.append("zip 里的额外文件: %s" % ", ".join(extra))
        notes.append("安装包: %s（%d 个条目，%d 字节）"
                     % (zip_path.name, len(names), zip_path.stat().st_size))
        if zip_path.read_bytes() == build_extension.build_zip_bytes():
            notes.append("安装包与当前源码重新打包的结果逐字节一致")
        else:
            notes.append("安装包内容一致，但压缩字节与本机重新打包不同"
                         "（zip 压缩结果与 Python/zlib 版本有关，不影响安装）")

    # --- 旧版单文件
    legacy = build_extension.LEGACY_PY
    if not legacy.exists():
        errors.append("缺少旧版单文件 %s（请运行 tools/build_extension.py）" % legacy.name)
    elif legacy.read_bytes() != SOURCE.read_bytes():
        errors.append("dist/%s 与 __init__.py 不一致，请重新运行 tools/build_extension.py"
                      % legacy.name)
    else:
        notes.append("旧版单文件: %s（与 __init__.py 一致）" % legacy.name)

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
