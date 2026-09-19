"""覆盖率审计：别名表相对 Blender 官方菜单是否**漏了条目**。

    python tools/extract_add_menu.py      # 先生成 add_menu_tree.json
    python tools/extract_node_menu.py     # 先生成 node_menu_tree.json
    python tools/audit_coverage.py

对照关系：

* 3D 视图「添加」菜单：逐条比对 `add_menu_tree.json` 里的 (算子, 属性) 与插件
  `ALIAS_CATEGORIES`；枚举型子菜单（灯光/融球/力场/探针）单独列出，需人工核对。
* 节点菜单：逐条比对四种节点树的 `NODE_ALIAS_GROUPS`，并检查
  `node.add_zone`（区域）/`node.add_typed_bundle`/`node.add_empty_group`
  以及共享 Layout/Group 菜单里的条目是否被 `NODE_EXTRA_ALIASES` 覆盖。

发现遗漏时以非零状态退出（可用于 CI）。
"""

import ast
import json
import pathlib
import sys

# Windows GBK 控制台可能编不出部分符号
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
ADDON = ROOT / "__init__.py"

BL_UI = None
for candidate in (pathlib.Path(__file__).parents[1] / "tools",):
    pass

# 节点菜单里由辅助函数（非 node.add_node）绘制、需要手工补充的条目
NODE_HELPERS = {
    "simulation_zone": ("node.add_zone", "Simulation"),
    "repeat_zone": ("node.add_zone", "Repeat"),
    "for_each_element_zone": ("node.add_zone", "For Each Element"),
    "closure_zone": ("node.add_zone", "Closure"),
    "typed_bundle": ("node.add_typed_bundle", "Typed Bundle"),
    "new_empty_group": ("node.add_empty_group", "New Group"),
}

# node_add_menu.py 里共享的基础菜单（四种节点树都会用到）
# (分类, 英文标签, 算子, 节点类型或 None)
SHARED_MENU_ITEMS = (
    ("Layout", "Frame", "node.add_node", "NodeFrame"),
    ("Layout", "Reroute", "node.add_node", "NodeReroute"),
    ("Group", "New Group", "node.add_empty_group", None),
    ("Group", "Group Input", "node.add_node", "NodeGroupInput"),
    ("Group", "Group Output", "node.add_node", "NodeGroupOutput"),
)

# 菜单里本身就带这些算子的条目不用做别名
IGNORED_OPERATORS = ("WM_OT_search_single_menu",)

# 设计上不覆盖的条目（动态内容或搜索专用），审计时只提示
DYNAMIC_NOTES = (
    "用户自定义节点组（node.add_node + node_tree 参数，随文件变化）",
    "资产架条目（template_node_asset_menu_items，随资产库变化）",
    "第三方插件用 nodeitems_utils 注册的节点分类",
    "搜索专用的「节点 ▸ 枚举项」条目（Blender 按当前界面语言生成，中文界面下本就可搜）",
)

# 枚举型子菜单的预期条目数（人工核对用；Blender 大版本升级后需要复核）
# 注：object.collection_instance_add 在官方菜单里是「每个集合一项」的枚举子菜单，
#     别名表只用默认集合添加一条，故预期为 1。
ENUM_EXPECTED = {
    "object.light_add": 4,
    "object.metaball_add": 5,
    "object.lightprobe_add": 3,
    "object.effector_add": 13,
    "object.empty_add": 8,
    "object.collection_instance_add": 1,
}


def load_addon_tables():
    tree = ast.parse(ADDON.read_text(encoding="utf-8"))
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            name = getattr(node.targets[0], "id", "")
            if name in ("ALIAS_CATEGORIES", "NODE_ALIAS_GROUPS", "NODE_EXTRA_ALIASES"):
                tables[name] = ast.literal_eval(node.value)
    return tables


def object_menu_items():
    """展开 3D 视图「添加」菜单，返回 (显式条目, 枚举型菜单)。"""
    data = json.loads((TOOLS / "add_menu_tree.json").read_text(encoding="utf-8-sig"))
    menus = data["menus"]
    items = []
    enum_menus = []
    seen = set()

    def visit(idname, path):
        if idname in seen or idname not in menus:
            return
        seen.add(idname)
        info = menus[idname]
        for entry in info["entries"]:
            kind = entry.get("kind")
            if kind == "menu":
                label = entry.get("text") or entry["menu"]
                visit(entry["menu"], path + (label,))
            elif kind == "op":
                props = dict(entry.get("assign") or {})
                props.update({k: v for k, v in (entry.get("props") or {}).items()})
                items.append({
                    "key": (entry["op"], tuple(sorted(props.items()))),
                    "path": path,
                    "label": entry.get("text"),
                    "op": entry["op"],
                    "props": props,
                })
            elif kind == "enum_menu":
                enum_menus.append({"op": entry["op"], "prop": entry["prop"],
                                   "path": path, "label": entry.get("text")})

    for entry in menus["VIEW3D_MT_add"]["entries"]:
        kind = entry.get("kind")
        if kind == "menu":
            label = entry.get("text") or entry["menu"]
            visit(entry["menu"], (label,))
        elif kind == "op":
            props = dict(entry.get("assign") or {})
            props.update({k: v for k, v in (entry.get("props") or {}).items()})
            items.append({"key": (entry["op"], tuple(sorted(props.items()))),
                          "path": (), "label": entry.get("text"), "op": entry["op"],
                          "props": props})
        elif kind == "enum_menu":
            enum_menus.append({"op": entry["op"], "prop": entry["prop"], "path": (),
                               "label": entry.get("text")})
    return items, enum_menus


def alias_object_keys(alias_categories):
    keys = set()
    for _zh, _en, _icon, _context, items in alias_categories:
        for _zh2, _en2, op, props, _icon2 in items:
            keys.add((op, tuple(sorted((props or {}).items()))))
    return keys


def node_tree_files():
    import os
    default = r"D:\steam\steamapps\common\Blender\5.2\scripts\startup\bl_ui"
    bl_ui = pathlib.Path(os.environ.get("BLENDER_BL_UI") or default)
    return bl_ui, {
        "ShaderNodeTree": "node_add_menu_shader.py",
        "GeometryNodeTree": "node_add_menu_geometry.py",
        "CompositorNodeTree": "node_add_menu_compositor.py",
        "TextureNodeTree": "node_add_menu_texture.py",
    }


def node_menu_items():
    """扫描节点菜单源码，返回 (node_operator 条目, 辅助函数条目)。"""
    bl_ui, files = node_tree_files()
    operators = []      # (树, 分类, 节点类型)
    helpers = []        # (树, 分类, 英文标签, 算子)
    for tree_type, filename in files.items():
        path = bl_ui / filename
        if not path.exists():
            print("  跳过（找不到 %s）: %s" % (filename, bl_ui))
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in ast.walk(module):
            if not isinstance(cls, ast.ClassDef):
                continue
            label = None
            menu_path = None
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                    target = ast.unparse(stmt.targets[0])
                    if target == "bl_label":
                        label = stmt.value.value
                    elif target == "menu_path":
                        menu_path = stmt.value.value
            category = menu_path or label or cls.name
            for call in ast.walk(cls):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                name = call.func.attr
                if name in ("node_operator", "node_operator_with_subnames",
                            "node_operator_with_searchable_enum",
                            "node_operator_with_searchable_enum_socket"):
                    idx = 1 if name == "node_operator" else 2
                    if len(call.args) > idx and isinstance(call.args[idx], ast.Constant):
                        operators.append((tree_type, category, call.args[idx].value))
                elif name in NODE_HELPERS:
                    operator_id, english = NODE_HELPERS[name]
                    helpers.append((tree_type, category, english, operator_id))
    return operators, helpers


def main():
    tables = load_addon_tables()
    problems = []

    # ---------------- 3D 视图「添加」菜单
    print("=" * 72)
    print("3D 视图「添加」菜单（VIEW3D_MT_add）")
    print("=" * 72)
    items, enum_menus = object_menu_items()
    alias_keys = alias_object_keys(tables["ALIAS_CATEGORIES"])
    missing = [item for item in items if item["key"] not in alias_keys]
    menu_keys = {item["key"] for item in items}
    enum_operators = {entry["op"] for entry in enum_menus}
    # 枚举型算子的条目由枚举项画出，别名表按「逐枚举项」覆盖，单独统计
    extra = sorted(key for key in alias_keys
                   if key not in menu_keys and key[0] not in enum_operators)
    missing = [item for item in missing if item["op"] not in IGNORED_OPERATORS]
    print("菜单显式条目: %d，别名表覆盖: %d，缺失: %d，别名表多余: %d"
          % (len(items), len(items) - len(missing), len(missing), len(extra)))
    for item in missing:
        print("  [缺失] %-28s %-42s props=%s"
              % ("/".join(item["path"]) or "-", item["op"], item["props"] or "{}"))
    for key in extra:
        print("  [多余] %s %s（官方菜单里已不存在）" % (key[0], dict(key[1]) or ""))
    if missing:
        problems.append("3D 视图添加菜单缺失 %d 条" % len(missing))

    print("\n枚举型子菜单（每个枚举项都会被画出来；下面是别名表里的覆盖条数）:")
    for entry in sorted(enum_menus, key=lambda item: item["op"]):
        count = sum(1 for key in alias_keys if key[0] == entry["op"])
        expected = ENUM_EXPECTED.get(entry["op"])
        mark = "[OK]  " if expected is None or count == expected else "[核对]"
        print("  %s %-32s %-28s 别名 %d 条%s"
              % (mark, "/".join(entry["path"]) or "-", "%s.%s" % (entry["op"], entry["prop"]),
                 count, "" if expected is None else "（预期 %d）" % expected))
    if extra:
        problems.append("3D 视图别名表有 %d 条已过期" % len(extra))

    # ---------------- 节点菜单
    print()
    print("=" * 72)
    print("节点编辑器「添加」菜单")
    print("=" * 72)
    node_table = {}
    for tree_type, groups in tables["NODE_ALIAS_GROUPS"].items():
        keys = set()
        for _path, group_items in groups:
            for idname, override in group_items:
                keys.add((idname, override))
        node_table[tree_type] = keys

    extra_table = set()
    for trees, path, english, operator_id, _node_type, _props, _condition in tables.get(
            "NODE_EXTRA_ALIASES", ()):
        for tree in (node_table if trees == "*" else trees):
            # 只按 (树, 分类, 标签, 算子) 比对，节点类型字段不参与匹配
            extra_table.add((tree, path, english, operator_id))

    operators, helpers = node_menu_items()
    # 只按节点类型 ID 比对（菜单里有些条目带自定义标签，如 "CSV (.csv)"）
    missing_ops = [row for row in operators
                   if row[2] not in {idname for idname, _override in node_table.get(row[0], set())}]
    print("node_operator 条目: %d，缺失: %d" % (len(operators), len(missing_ops)))
    for tree, category, idname in missing_ops:
        print("  [缺失] %-16s %-22s %s" % (tree, category, idname))
    if missing_ops:
        problems.append("节点菜单缺失 %d 条 node_operator 条目" % len(missing_ops))

    if helpers:
        print("\n辅助函数绘制的条目（需要 NODE_EXTRA_ALIASES 覆盖）:")
        for tree, category, english, operator_id in helpers:
            covered = (tree, category, english, operator_id) in extra_table
            print("  %s %-16s %-22s %-24s %s"
                  % ("[已覆盖]" if covered else "[缺失]  ", tree, category, english, operator_id))
            if not covered:
                problems.append("节点补充条目缺失: %s / %s / %s" % (tree, category, english))

    print("\n共享基础菜单（Layout / Group）:")
    for category, english, operator_id, node_type in SHARED_MENU_ITEMS:
        # 覆盖来源可能是自动生成的表（几何/合成树自带 Input/Group、Output 分类），
        # 也可能是手工补充表（着色器/纹理树的 Group 菜单）
        generated = sorted(tree for tree, keys in node_table.items()
                           if node_type and any(key[0] == node_type for key in keys))
        extras = sorted(tree for tree in node_table
                        if (tree, category, english, operator_id) in extra_table)
        covered = bool(generated or extras)
        where = []
        if generated:
            where.append("生成表:%s" % ",".join(generated))
        if extras:
            where.append("补充表:%s" % ",".join(extras))
        print("  %s %-10s %-14s %-22s %s"
              % ("[已覆盖]" if covered else "[缺失]  ", category, english, operator_id,
                 " ".join(where)))
        if not covered:
            problems.append("共享菜单条目缺失: %s / %s" % (category, english))

    print("\n设计上不覆盖（已知动态内容）:")
    for note in DYNAMIC_NOTES:
        print("  - %s" % note)

    print()
    if problems:
        print("发现 %d 类问题:" % len(problems))
        for problem in problems:
            print("  [x] %s" % problem)
        return 1
    print("覆盖检查通过 [OK]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
