# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，版本号与插件 `bl_info`、
扩展 manifest 保持一致（打包脚本会自动读取 `bl_info`）。

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
