# tools/

开发/维护脚本，**终端用户不需要运行**。它们负责把 Blender 自带菜单里的真实条目
提取出来，再写回插件源码，保证别名表与官方菜单（以及官方中文译名）一致。

依赖：Python 3.10+（纯标准库，不需要 bpy）。默认从下面的路径读取 Blender 自带的
`bl_ui` 源码，可用环境变量覆盖：

```powershell
$env:BLENDER_BL_UI = 'D:\steam\steamapps\common\Blender\5.2\scripts\startup\bl_ui'
```

```bash
export BLENDER_BL_UI=/usr/share/blender/5.2/scripts/startup/bl_ui
```

## 脚本

| 脚本 | 作用 |
| --- | --- |
| `extract_add_menu.py` | 解析 `bl_ui/space_view3d.py` 里 3D 视图「添加」菜单的真实条目（算子、枚举属性、图标、调用上下文），输出 `add_menu_tree.json` |
| `extract_node_menu.py` | 解析 `bl_ui/node_add_menu_*.py`，输出 `node_menu_tree.json`：四种节点树的分类结构与节点类型 ID |
| `build_node_table.py` | 把 `node_menu_tree.json` 写回根目录 `__init__.py` 中 `# === BEGIN/END GENERATED NODE TABLE ===` 标记之间（幂等，可反复运行） |
| `build_extension.py` | 生成根目录 `blender_manifest.toml`、`dist/bilingual_add_search-<版本>.zip`（扩展包）与 `dist/bilingual_add_search.py`（旧版单文件）；版本号取自 `__init__.py` 的 `bl_info`，zip 固定时间戳可重现 |
| `check_package.py` | 校验 manifest 与 `bl_info` 一致、zip 内文件与源码逐字节一致、zip 结构可被 Blender 安装、旧版单文件与源码一致（CI 也会跑） |
| `audit_coverage.py` | **覆盖率审计**：把别名表与 Blender 官方菜单逐条对照，列出缺失/过期条目与未覆盖的枚举型子菜单；发现缺失时以非零状态退出 |

常用流程：

```bash
# 改了插件代码后（同步 manifest 与发行产物）
python tools/build_extension.py
python tools/check_package.py

# Blender 大版本升级后：重建别名表并检查有没有漏条目
python tools/extract_add_menu.py        # 3D 视图菜单 → add_menu_tree.json
python tools/extract_node_menu.py       # 节点菜单 → node_menu_tree.json
python tools/build_node_table.py        # 写回 __init__.py（自动生成部分）
python tools/audit_coverage.py          # ← 逐条对照官方菜单，报告缺失/过期
python tools/build_extension.py
python tools/check_package.py
```

> - 3D 视图那 77 条别名（`ALIAS_CATEGORIES`）与节点侧 12 条补充条目
>   （`NODE_EXTRA_ALIASES`：区域/类型化捆包/框/转接/新建组/组输入输出）是**手写表格**，
>   `audit_coverage.py` 负责告诉你有没有漏、有没有过期；
> - 节点表（642 条）由 `build_node_table.py` 自动生成；
> - 所有中文名都取自 Blender 自带的 `zh_HANS` 词条，与官方界面一致。

> `audit_coverage.py` 的「辅助函数绘制的条目」与「共享基础菜单」两部分需要读取
> Blender 自带的 `bl_ui` 源码（`BLENDER_BL_UI`），因此建议在装了 Blender 的机器上跑。

## 数据文件

| 文件 | 内容 |
| --- | --- |
| `add_menu_tree.json` | 3D 视图「添加」菜单的真实条目树（供人工核对） |
| `node_menu_tree.json` | 节点菜单分类与节点 ID（`build_node_table.py` 的输入） |
| `zh_terms.json` | 用到的官方简体中文译名快照（含翻译上下文） |

## 运行环境

这些脚本在 **Blender 5.2.2 LTS** 上生成并验证过当前版本的数据；
插件本身兼容 Blender 3.x ～ 5.x。
