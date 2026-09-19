"""Extract the real Add-menu item tree from Blender's bundled bl_ui python sources.

Pure-static AST analysis (no bpy needed). Writes ``tools/add_menu_tree.json`` so the
information baked into the addon matches the labels Blender actually draws.

Usage:
    python tools/extract_add_menu.py

The bl_ui directory is taken from BLENDER_BL_UI when set, otherwise from the default
path below (edit it for your machine), e.g.
    BLENDER_BL_UI=/usr/share/blender/5.2/scripts/startup/bl_ui
"""

import ast
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUTPUT = HERE / "add_menu_tree.json"

DEFAULT_BL_UI = r"D:\steam\steamapps\common\Blender\5.2\scripts\startup\bl_ui"

BL_UI = pathlib.Path(os.environ.get("BLENDER_BL_UI") or DEFAULT_BL_UI)

# Menu idnames reachable from the object-mode Add menu (Shift+A in the 3D View).
ROOTS = ["VIEW3D_MT_add"]


def collect_menus():
    menus = {}
    for path in sorted(BL_UI.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(b) for b in node.bases]
            if "Menu" not in bases and "bpy.types.Menu" not in bases:
                continue
            draw = None
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "draw":
                    draw = item
            if draw is None:
                continue
            idname = node.name
            for item in node.body:
                if isinstance(item, ast.Assign):
                    tgt = ast.unparse(item.targets[0])
                    if tgt == "bl_idname" and isinstance(item.value, ast.Constant):
                        idname = item.value.value
            menus[idname] = (node.name, draw, str(path))
    return menus


def call_name(func):
    if isinstance(func, ast.Call):
        func = func.func
    return ast.unparse(func)


def call_receiver(call):
    """返回 ``xxx.yyy(...)`` 里的接收者名字（``xxx``），否则 None。"""
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def layout_derived_names(draw_func):
    """收集由 ``layout`` 派生的局部变量名（layout / col / row / sub …）。

    菜单里不少条目画在 ``col = layout.column()`` 这类变量上，只认 ``layout.``
    会漏掉它们（例如「集合实例」）。
    """
    names = {"layout"}
    changed = True
    while changed:
        changed = False
        for stmt in ast.walk(draw_func):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if (isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call)
                        and call_receiver(stmt.value) in names and target.id not in names):
                    names.add(target.id)
                    changed = True
    return names


def parse_call(call, layout_names=("layout",)):
    """把一个 ``layout.xxx(...)`` 调用解析成条目 dict，否则返回 None。"""
    if call_receiver(call) not in layout_names:
        return None
    fname = call_name(call)
    kind = fname.split(".")[-1]
    kw = {}
    for k in call.keywords:
        if k.arg in ("text", "icon", "text_ctxt"):
            try:
                kw[k.arg] = ast.literal_eval(k.value)
            except ValueError:
                kw[k.arg] = ast.unparse(k.value)
    if kind == "operator":
        op = ast.literal_eval(call.args[0]) if call.args else None
        return {"kind": "op", "op": op, "text": kw.get("text"), "icon": kw.get("icon")}
    if kind == "operator_menu_enum":
        op = ast.literal_eval(call.args[0]) if call.args else None
        prop = ast.literal_eval(call.args[1]) if len(call.args) > 1 else None
        return {
            "kind": "enum_menu",
            "op": op,
            "prop": prop,
            "text": kw.get("text"),
            "icon": kw.get("icon"),
        }
    if kind == "operator_enum":
        # 每个枚举项都会画一个按钮（光照/融球/探针子菜单就是这种）
        op = ast.literal_eval(call.args[0]) if call.args else None
        prop = ast.literal_eval(call.args[1]) if len(call.args) > 1 else None
        return {"kind": "enum_menu", "op": op, "prop": prop,
                "text": kw.get("text"), "icon": kw.get("icon")}
    if kind == "menu":
        menu = ast.literal_eval(call.args[0]) if call.args else None
        return {"kind": "menu", "menu": menu, "text": kw.get("text"), "icon": kw.get("icon")}
    return None


def parse_entry(stmt, layout_names=("layout",)):
    """Return a dict for one menu-drawing statement, or None."""
    # 形式 1: layout.operator("id", text=..., icon=...).type = 'X'
    if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Attribute):
        target = stmt.targets[0]
        if isinstance(target.value, ast.Call):
            entry = parse_call(target.value, layout_names)
            if entry is not None:
                try:
                    value = ast.literal_eval(stmt.value)
                except (ValueError, SyntaxError):
                    value = ast.unparse(stmt.value)
                entry.setdefault("assign", {})[target.attr] = value
            return entry
    # 形式 2: layout.xxx(...)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return parse_call(stmt.value, layout_names)
    return None


def walk_body(body, layout_names=("layout",)):
    out = []
    for stmt in body:
        entry = parse_entry(stmt, layout_names)
        if entry is not None:
            out.append(entry)
            continue
        for field in ("body", "orelse", "finalbody"):
            sub = getattr(stmt, field, None)
            if sub:
                out.extend(walk_body(sub, layout_names))
    return out


def main():
    menus = collect_menus()
    seen = set()
    result = {}

    def visit(idname):
        if idname in seen or idname not in menus:
            return
        seen.add(idname)
        cls_name, draw, path = menus[idname]
        entries = walk_body(draw.body, layout_derived_names(draw))
        result[idname] = {"class": cls_name, "file": pathlib.Path(path).name, "entries": entries}
        for e in entries:
            if e["kind"] == "menu" and e.get("menu"):
                visit(e["menu"])

    for root in ROOTS:
        visit(root)

    # Blender's own menu labels for the same idname may live in several classes;
    # report anything referenced but missing so it is not silently dropped.
    missing = sorted(
        {
            e["menu"]
            for info in result.values()
            for e in info["entries"]
            if e["kind"] == "menu" and e.get("menu") not in menus
        }
    )

    payload = {"menus": result, "missing": missing}
    if len(sys.argv) > 1 and sys.argv[1] == "-":
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
        return
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    entry_count = sum(len(info["entries"]) for info in result.values())
    print("bl_ui: %s" % BL_UI)
    print("menus: %d, entries: %d, missing: %d" % (len(result), entry_count, len(missing)))
    print("written: %s" % OUTPUT)


if __name__ == "__main__":
    main()
