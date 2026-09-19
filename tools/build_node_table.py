"""Regenerate the NODE_ALIAS_GROUPS table inside the add-on package.

Reads tools/node_menu_tree.json (produced by tools/extract_node_menu.py) and
rewrites everything between the two marker comments in ``__init__.py``.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "__init__.py"
TREE_JSON = ROOT / "tools" / "node_menu_tree.json"

BEGIN = "# === BEGIN GENERATED NODE TABLE ==="
END = "# === END GENERATED NODE TABLE ==="

TREE_ORDER = ("ShaderNodeTree", "CompositorNodeTree", "TextureNodeTree", "GeometryNodeTree")


def render(data):
    lines = ["NODE_ALIAS_GROUPS = {"]
    for tree_type in TREE_ORDER:
        groups = data.get(tree_type) or {}
        if not groups:
            continue
        lines.append('    "%s": (' % tree_type)
        for path, info in groups.items():
            items = []
            seen = set()
            for idname, label in info["items"]:
                key = (idname, label)
                if key in seen:
                    continue
                seen.add(key)
                items.append((idname, label))
            if not items:
                continue
            lines.append('        ("%s", (' % path)
            for idname, label in items:
                label_repr = "None" if label is None else '"%s"' % label.replace('"', '\\"')
                lines.append('            ("%s", %s),' % (idname, label_repr))
            lines.append("        )),")
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines)


def main():
    data = json.loads(TREE_JSON.read_text(encoding="utf-8-sig"))
    table = render(data)

    source = SOURCE.read_text(encoding="utf-8")
    start = source.index(BEGIN)
    end = source.index(END)
    updated = source[:start] + BEGIN + "\n" + table + "\n" + source[end:]
    SOURCE.write_text(updated, encoding="utf-8", newline="\n")

    item_count = sum(len(info["items"]) for groups in data.values() for info in groups.values())
    print("trees:", len(data), "categories:", sum(len(g) for g in data.values()), "items:", item_count)
    print("bytes:", len(updated))


if __name__ == "__main__":
    main()
