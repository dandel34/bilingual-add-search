# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，版本号与插件 `bl_info`、
扩展 manifest 保持一致（打包脚本会自动读取 `bl_info`）。

## 1.3.0

- **补齐节点菜单里非 `node.add_node` 绘制的条目**（这些以前搜不到，共 12 条）：
  - 几何节点：模拟区域 `Simulation`、遍历元素区域 `For Each Element`、重复区域 `Repeat`、
    闭包区域 `Closure`、类型化捆包 `Typed Bundle`
  - 着色器节点：重复区域 `Repeat`、闭包区域 `Closure`
  - 四种节点树通用：框 `Frame`、转接点 `Reroute`、新建组 `New Group`、
    组输入/组输出 `Group Input/Output`（仅在编辑节点组时显示，与官方菜单一致）
- 新增 `tools/audit_coverage.py`：把别名表与 Blender 官方菜单逐条对照，列出缺失/过期条目，
  发现问题时以非零状态退出（可用作定期检查）
- 修正 `tools/extract_add_menu.py` 的两个解析盲点：
  `layout.operator(...).type = 'X'` 形式的条目（空物体/蜡笔/晶格等）、
  以及画在 `col = layout.column()` 这类派生变量上的条目（如「集合实例」）
- 修掉补充条目包装形状导致的菜单绘制解包错误；去掉几何/合成树里与官方 `Input/Group`、
  `Output` 分类重复的组输入/组输出条目
- 「多余」「缺失」自检：3D 视图 53 条显式条目全覆盖，节点 642 条无缺失

## 仓库打包方式（不影响版本号）

- 仓库根目录改为**标准扩展包结构**：`__init__.py` + `blender_manifest.toml`，
  因此仓库的 `Code ▸ Download ZIP` 可以直接在 Blender 4.2+ 里「从磁盘安装」。
- `tools/build_extension.py` 负责生成 manifest 与 `dist/`（扩展 zip + 旧版单文件），
  zip 使用固定时间戳，可重现构建；`tools/check_package.py` 在 CI 里校验一致性。

## 1.2.0

- 搜索结果前缀由 `中英双语节点搜索 Bilingual Node Aliases` 缩短为 **`BNA`**
  （物体菜单与节点菜单共用），并新增偏好项 **搜索前缀** 可自定义，留空回落到 `BNA`。
- 两个别名根菜单的 `bl_label` 同步设为 `BNA`，作为搜索路径前缀的兜底。

## 1.1.0

- 新增节点编辑器支持：**着色器（材质）/ 合成 / 纹理 / 几何** 四种节点树的「添加」菜单
  双语别名，共 642 条、88 个分类。
- 节点英文名实时读 RNA（`bl_rna.name`），中文名实时查 Blender 自带 `zh_HANS/zh_HANT`
  词条，随 Blender 升级自动更新。
- 节点条目按当前节点树类型自动切换，调用参数与官方菜单一致（`node.add_node` + `use_transform`）。

## 1.0.0

- 首个版本：3D 视图物体模式「添加」菜单（Shift+A）双语别名，77 条、13 个分类。
- 一键切换界面语言（`Shift+Alt+L`，语言对可配置）。
