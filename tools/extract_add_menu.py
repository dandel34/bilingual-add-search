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


def parse_entry(stmt):
    """Return a dict for one menu-drawing statement, or None."""
    # layout.operator("id", text=..., icon=...) possibly with `.type = 'X'`
    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        target = ast.unparse(stmt.targets[0])
        if target.endswith(".type") or target.endswith(".props"):
            outer = call.func.value if isinstance(call.func, ast.Call) else None
            if outer is None:
                return None
            entry = parse_entry(outer)
            if entry is None:
                return None
            key = target.rsplit(".", 1)[-1]
            val = stmt.value.args[0] if stmt.value.args else None
            value = ast.literal_eval(stmt.value.args[0]) if stmt.value.args else ast.unparse(
                stmt.value.keywords[0].value
            )
            entry.setdefault("props", {})
            entry["props"]["__setattr__"] = value
            entry["attr"] = key
            return entry
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return None
    call = stmt.value
    fname = call_name(call)
    if not fname.startswith("layout."):
        return None
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
    if kind == "menu":
        menu = ast.literal_eval(call.args[0]) if call.args else None
        return {"kind": "menu", "menu": menu, "text": kw.get("text"), "icon": kw.get("icon")}
    if kind == "menu_enum" or kind == "operator_enum":
        return {"kind": "ignore", "detail": fname}
    return None


def walk_body(body):
    out = []
    for stmt in body:
        entry = parse_entry(stmt)
        if entry is not None:
            out.append(entry)
            continue
        for field in ("body", "orelse", "finalbody"):
            sub = getattr(stmt, field, None)
            if sub:
                out.extend(walk_body(sub))
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
        entries = walk_body(draw.body)
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
