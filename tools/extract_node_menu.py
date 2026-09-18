"""Extract node add-menu items (category groups + node type idnames) from bl_ui sources.

Writes ``tools/node_menu_tree.json``: {tree_type: {category_path: {items: [...]}}}

Node type idnames are the stable identifiers used by `node.add_node(type=...)`;
labels are resolved later from RNA + Blender's own zh translation catalog, so the
table only needs the identifiers and the category structure.

Usage:
    python tools/extract_node_menu.py
    BLENDER_BL_UI=/usr/share/blender/5.2/scripts/startup/bl_ui python tools/extract_node_menu.py
"""

import ast
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUTPUT = HERE / "node_menu_tree.json"

DEFAULT_BL_UI = r"D:\steam\steamapps\common\Blender\5.2\scripts\startup\bl_ui"

BL_UI = pathlib.Path(os.environ.get("BLENDER_BL_UI") or DEFAULT_BL_UI)

FILES = {
    "ShaderNodeTree": "node_add_menu_shader.py",
    "GeometryNodeTree": "node_add_menu_geometry.py",
    "CompositorNodeTree": "node_add_menu_compositor.py",
    "TextureNodeTree": "node_add_menu_texture.py",
}

CALL_LAYOUT_ARG_INDEX = {
    # self.node_operator(layout, "ShaderNodeX", ...)
    "node_operator": 1,
    # NOTE: the *_with_* helpers take `context` first, so the node idname is one
    # position later than the layout argument.
    # self.node_operator_with_searchable_enum(context, layout, "ShaderNodeX", "prop", ...)
    "node_operator_with_searchable_enum": 2,
    "node_operator_with_searchable_enum_socket": 2,
    "node_operator_with_subnames": 2,
}


def class_info(node):
    """Return (bl_label, menu_path, items) for a ClassDef."""
    bl_label = None
    menu_path = None
    items = []

    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            name = ast.unparse(stmt.targets[0])
            if name == "bl_label":
                bl_label = stmt.value.value
            elif name == "menu_path":
                menu_path = stmt.value.value

    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.Call):
            continue
        func = stmt.func
        if not isinstance(func, ast.Attribute) or not func.attr in CALL_LAYOUT_ARG_INDEX:
            continue
        idx = CALL_LAYOUT_ARG_INDEX[func.attr]
        if len(stmt.args) <= idx:
            continue
        arg = stmt.args[idx]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            continue
        label = None
        for kw in stmt.keywords:
            if kw.arg == "label" and isinstance(kw.value, ast.Constant):
                label = kw.value.value
        items.append((arg.value, label))
    return bl_label, menu_path, items


def main():
    out = {}
    for tree_type, filename in FILES.items():
        path = BL_UI / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        groups = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bl_label, menu_path, items = class_info(node)
            if not items:
                continue
            key = menu_path or bl_label or node.name
            groups[key] = {
                "class": node.name,
                "bl_label": bl_label,
                "menu_path": menu_path,
                "items": items,
            }
        out[tree_type] = groups

    if len(sys.argv) > 1 and sys.argv[1] == "-":
        json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
        return
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("bl_ui: %s" % BL_UI)
    for tree_type, groups in out.items():
        print("  %-18s categories: %2d, items: %d"
              % (tree_type, len(groups), sum(len(g["items"]) for g in groups.values())))
    print("written: %s" % OUTPUT)


if __name__ == "__main__":
    main()
