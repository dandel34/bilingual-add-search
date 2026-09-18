# SPDX-FileCopyrightText: 2026 Bilingual Add Search contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bilingual Add Search / 中英双语添加搜索.

Shift+A 打开「添加」菜单后，搜索框里输入中文或英文都能找到同一个条目。

原理（Blender 5.x 源码 ``interface_template_search_menu.cc``）：
    搜索模板把每个菜单项展开成 ``"<菜单路径> ‣ <按钮文本>"`` 再做字符串匹配，
    并且会递归展开所有子菜单。因此只要把「中英双语标签」的别名条目挂进
    ``VIEW3D_MT_add``，原生搜索框就能同时用中文和英文命中。

本插件不改动 Blender 自带的菜单内容，只是在「添加」菜单末尾附加一个
别名子菜单；条目图标、算子调用上下文都与官方菜单保持一致。
"""

bl_info = {
    "name": "Bilingual Add Search (中英双语添加搜索)",
    "author": "DSH",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "location": ("3D 视图 → 添加菜单 (Shift+A) / 着色器·合成·几何·纹理节点编辑器 → 添加菜单 (Shift+A)"
                 " / 偏好设置 → 插件"),
    "description": "添加菜单与节点菜单：中文、英文关键词都能搜到同一个条目；附一键切换中英文界面",
    "category": "Interface",
}

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences, Menu, Operator

# ---------------------------------------------------------------------------
# 别名数据
#
# 结构: (分类中文, 分类英文, 分类图标, 算子调用上下文, 条目...)
# 条目: (中文名, 英文名, 算子 idname, 属性 dict 或 None, 图标)
#
# 中文名取自 Blender 自带 zh_HANS 翻译（datafiles/locale/zh_HANS），
# 英文名与图标、属性取自 bl_ui/space_view3d.py 中真实的添加菜单定义，
# 保证与官方菜单显示的名称一致。
# ---------------------------------------------------------------------------

ALIAS_CATEGORIES = (
    ("网格", "Mesh", 'OUTLINER_OB_MESH', 'INVOKE_REGION_WIN', (
        ("平面", "Plane", "mesh.primitive_plane_add", None, 'MESH_PLANE'),
        ("立方体", "Cube", "mesh.primitive_cube_add", None, 'MESH_CUBE'),
        ("圆形", "Circle", "mesh.primitive_circle_add", None, 'MESH_CIRCLE'),
        ("经纬球", "UV Sphere", "mesh.primitive_uv_sphere_add", None, 'MESH_UVSPHERE'),
        ("棱角球", "Ico Sphere", "mesh.primitive_ico_sphere_add", None, 'MESH_ICOSPHERE'),
        ("柱体", "Cylinder", "mesh.primitive_cylinder_add", None, 'MESH_CYLINDER'),
        ("锥形", "Cone", "mesh.primitive_cone_add", None, 'MESH_CONE'),
        ("环体", "Torus", "mesh.primitive_torus_add", None, 'MESH_TORUS'),
        ("栅格", "Grid", "mesh.primitive_grid_add", None, 'MESH_GRID'),
        ("猴头", "Monkey", "mesh.primitive_monkey_add", None, 'MESH_MONKEY'),
    )),
    ("曲线", "Curve", 'OUTLINER_OB_CURVE', 'INVOKE_REGION_WIN', (
        ("贝塞尔曲线", "Bezier", "curve.primitive_bezier_curve_add", None, 'CURVE_BEZCURVE'),
        ("贝塞尔圆环", "Bezier Circle", "curve.primitive_bezier_circle_add", None, 'CURVE_BEZCIRCLE'),
        ("NURBS 曲线", "Nurbs Curve", "curve.primitive_nurbs_curve_add", None, 'CURVE_NCURVE'),
        ("NURBS 圆环", "Nurbs Circle", "curve.primitive_nurbs_circle_add", None, 'CURVE_NCIRCLE'),
        ("路径", "Path", "curve.primitive_nurbs_path_add", None, 'CURVE_PATH'),
        ("空白毛发", "Empty Hair", "object.curves_empty_hair_add", None, 'CURVES_DATA'),
        ("毛发", "Fur", "object.quick_fur", None, 'CURVES_DATA'),
        ("随机曲线", "Random Curves", "object.curves_random_add", None, 'CURVES_DATA'),
    )),
    ("曲面", "Surface", 'OUTLINER_OB_SURFACE', 'INVOKE_REGION_WIN', (
        ("NURBS 曲线", "Nurbs Curve", "surface.primitive_nurbs_surface_curve_add", None, 'SURFACE_NCURVE'),
        ("NURBS 圆环", "Nurbs Circle", "surface.primitive_nurbs_surface_circle_add", None, 'SURFACE_NCIRCLE'),
        ("NURBS 曲面", "Nurbs Surface", "surface.primitive_nurbs_surface_surface_add", None, 'SURFACE_NSURFACE'),
        ("NURBS 圆柱", "Nurbs Cylinder", "surface.primitive_nurbs_surface_cylinder_add", None, 'SURFACE_NCYLINDER'),
        ("NURBS 球体", "Nurbs Sphere", "surface.primitive_nurbs_surface_sphere_add", None, 'SURFACE_NSPHERE'),
        ("NURBS 环体", "Nurbs Torus", "surface.primitive_nurbs_surface_torus_add", None, 'SURFACE_NTORUS'),
    )),
    ("融球", "Metaball", 'OUTLINER_OB_META', 'INVOKE_REGION_WIN', (
        ("球", "Ball", "object.metaball_add", {"type": 'BALL'}, 'META_BALL'),
        ("胶囊", "Capsule", "object.metaball_add", {"type": 'CAPSULE'}, 'META_CAPSULE'),
        ("平面", "Plane", "object.metaball_add", {"type": 'PLANE'}, 'META_PLANE'),
        ("椭球体", "Ellipsoid", "object.metaball_add", {"type": 'ELLIPSOID'}, 'META_ELLIPSOID'),
        ("立方体", "Cube", "object.metaball_add", {"type": 'CUBE'}, 'META_CUBE'),
    )),
    ("文本/点云/其他", "Text & Others", 'OUTLINER_OB_FONT', 'EXEC_REGION_WIN', (
        ("文本", "Text", "object.text_add", None, 'OUTLINER_OB_FONT'),
        ("点云", "Point Cloud", "object.pointcloud_random_add", None, 'OUTLINER_OB_POINTCLOUD'),
        ("扬声器", "Speaker", "object.speaker_add", None, 'OUTLINER_OB_SPEAKER'),
        ("集合实例", "Collection Instance", "object.collection_instance_add", None,
         'OUTLINER_OB_GROUP_INSTANCE'),
    )),
    ("蜡笔", "Grease Pencil", 'OUTLINER_OB_GREASEPENCIL', 'EXEC_REGION_WIN', (
        ("空白蜡笔", "Blank", "object.grease_pencil_add", {"type": 'EMPTY'}, 'EMPTY_AXIS'),
        ("笔画", "Stroke", "object.grease_pencil_add", {"type": 'STROKE'}, 'STROKE'),
        ("猴头", "Monkey", "object.grease_pencil_add", {"type": 'MONKEY'}, 'MONKEY'),
        ("场景线条画", "Scene Line Art", "object.grease_pencil_add", {"type": 'LINEART_SCENE'},
         'SCENE_DATA'),
        ("集合线条画", "Collection Line Art", "object.grease_pencil_add",
         {"type": 'LINEART_COLLECTION'}, 'OUTLINER_COLLECTION'),
        ("物体线条画", "Object Line Art", "object.grease_pencil_add", {"type": 'LINEART_OBJECT'},
         'OBJECT_DATA'),
    )),
    ("骨架/晶格", "Armature & Lattice", 'OUTLINER_OB_ARMATURE', 'EXEC_REGION_WIN', (
        ("骨架", "Armature", "object.armature_add", None, 'OUTLINER_OB_ARMATURE'),
        ("单段骨骼", "Single Bone", "object.armature_add", None, 'BONE_DATA'),
        ("晶格", "Lattice", "object.add", {"type": 'LATTICE'}, 'OUTLINER_OB_LATTICE'),
        ("选中项晶格变形", "Lattice Deform Selected", "object.lattice_add_to_selected", None,
         'OUTLINER_OB_LATTICE'),
    )),
    ("空物体", "Empty", 'OUTLINER_OB_EMPTY', 'INVOKE_REGION_WIN', (
        ("纯轴", "Plain Axes", "object.empty_add", {"type": 'PLAIN_AXES'}, 'EMPTY_AXIS'),
        ("箭头", "Arrows", "object.empty_add", {"type": 'ARROWS'}, 'EMPTY_ARROWS'),
        ("单向箭头", "Single Arrow", "object.empty_add", {"type": 'SINGLE_ARROW'},
         'EMPTY_SINGLE_ARROW'),
        ("圆形空物体", "Empty Circle", "object.empty_add", {"type": 'CIRCLE'}, 'MESH_CIRCLE'),
        ("立方体空物体", "Empty Cube", "object.empty_add", {"type": 'CUBE'}, 'CUBE'),
        ("球形空物体", "Empty Sphere", "object.empty_add", {"type": 'SPHERE'}, 'SPHERE'),
        ("锥形空物体", "Empty Cone", "object.empty_add", {"type": 'CONE'}, 'CONE'),
        ("空图像", "Empty Image", "object.empty_add", {"type": 'IMAGE'}, 'FILE_IMAGE'),
    )),
    ("图像", "Image", 'OUTLINER_OB_IMAGE', 'EXEC_REGION_WIN', (
        ("参照图", "Reference", "object.empty_image_add", {"background": False}, 'IMAGE_REFERENCE'),
        ("背景图", "Background", "object.empty_image_add", {"background": True}, 'IMAGE_BACKGROUND'),
        ("图像网格平面", "Mesh Plane", "image.import_as_mesh_planes", None, 'MESH_PLANE'),
    )),
    ("灯光", "Light", 'OUTLINER_OB_LIGHT', 'INVOKE_REGION_WIN', (
        ("点光", "Point Light", "object.light_add", {"type": 'POINT'}, 'LIGHT_POINT'),
        ("日光", "Sun Light", "object.light_add", {"type": 'SUN'}, 'LIGHT_SUN'),
        ("聚光", "Spot Light", "object.light_add", {"type": 'SPOT'}, 'LIGHT_SPOT'),
        ("面光", "Area Light", "object.light_add", {"type": 'AREA'}, 'LIGHT_AREA'),
    )),
    ("光照探针", "Light Probe", 'OUTLINER_OB_LIGHTPROBE', 'INVOKE_REGION_WIN', (
        ("反射球", "Sphere", "object.lightprobe_add", {"type": 'SPHERE'}, 'LIGHTPROBE_CUBEMAP'),
        ("反射平面", "Plane", "object.lightprobe_add", {"type": 'PLANE'}, 'LIGHTPROBE_PLANAR'),
        ("辐照体积", "Volume", "object.lightprobe_add", {"type": 'VOLUME'}, 'LIGHTPROBE_GRID'),
    )),
    ("摄像机/音量", "Camera & Volume", 'OUTLINER_OB_CAMERA', 'EXEC_REGION_WIN', (
        ("摄像机", "Camera", "object.camera_add", None, 'OUTLINER_OB_CAMERA'),
        ("体积空物体", "Empty Volume", "object.volume_add", None, 'OUTLINER_DATA_VOLUME'),
        ("导入 OpenVDB", "Import OpenVDB", "object.volume_import", None, 'OUTLINER_DATA_VOLUME'),
    )),
    ("力场", "Force Field", 'OUTLINER_OB_FORCE_FIELD', 'EXEC_REGION_WIN', (
        ("力场", "Force", "object.effector_add", {"type": 'FORCE'}, 'FORCE_FORCE'),
        ("风力", "Wind", "object.effector_add", {"type": 'WIND'}, 'FORCE_WIND'),
        ("涡流", "Vortex", "object.effector_add", {"type": 'VORTEX'}, 'FORCE_VORTEX'),
        ("磁力", "Magnetic", "object.effector_add", {"type": 'MAGNET'}, 'FORCE_MAGNETIC'),
        ("谐振", "Harmonic", "object.effector_add", {"type": 'HARMONIC'}, 'FORCE_HARMONIC'),
        ("电荷", "Charge", "object.effector_add", {"type": 'CHARGE'}, 'FORCE_CHARGE'),
        ("兰纳琼斯分子力", "Lennard-Jones", "object.effector_add", {"type": 'LENNARDJ'},
         'FORCE_LENNARDJONES'),
        ("纹理力场", "Texture", "object.effector_add", {"type": 'TEXTURE'}, 'FORCE_TEXTURE'),
        ("曲线引导", "Curve Guide", "object.effector_add", {"type": 'GUIDE'}, 'FORCE_CURVE'),
        ("群体", "Boid", "object.effector_add", {"type": 'BOID'}, 'FORCE_BOID'),
        ("紊流", "Turbulence", "object.effector_add", {"type": 'TURBULENCE'}, 'FORCE_TURBULENCE'),
        ("拖拽", "Drag", "object.effector_add", {"type": 'DRAG'}, 'FORCE_DRAG'),
        ("流体流动", "Fluid Flow", "object.effector_add", {"type": 'FLUID'}, 'FORCE_FLUIDFLOW'),
    )),
)

ROOT_MENU_IDNAME = "BILINGUAL_MT_add_aliases"
NODE_ROOT_MENU_IDNAME = "BILINGUAL_MT_node_aliases"
TOGGLE_OPERATOR_IDNAME = "bilingual.toggle_ui_language"
DEFAULT_HOTKEY = {"type": 'L', "value": 'PRESS', "shift": True, "alt": True}
NODE_ADD_OPERATOR_IDNAME = "node.add_node"

# 搜索结果里的前缀（= 别名子菜单按钮的文本，Blender 用它拼出「前缀 ‣ 分类 ‣ 条目」）
DEFAULT_ALIAS_PREFIX = "BNA"

# ---------------------------------------------------------------------------
# 节点别名数据
#
# 结构: {节点树类型: ((分类路径, ((节点类型 ID, 菜单标签覆盖或 None), ...)), ...)}
#
# 分类路径与节点 ID 取自 bl_ui/node_add_menu_*.py（即 Blender 真实菜单内容）；
# 英文名由 RNA 读取（bl_rna.name，任何界面语言下都是英文原文），
# 中文名由 Blender 自带的 zh 翻译词条（datafiles/locale/*.mo）查出，
# 因此标签与官方界面保持一致，且随 Blender 升级自动更新。
# 重新生成: python tools/build_node_table.py
# ---------------------------------------------------------------------------

# === BEGIN GENERATED NODE TABLE ===
NODE_ALIAS_GROUPS = {
    "ShaderNodeTree": (
        ("Input", (
            ("ShaderNodeAmbientOcclusion", None),
            ("ShaderNodeAttribute", None),
            ("ShaderNodeBevel", None),
            ("ShaderNodeVertexColor", None),
            ("ShaderNodeFresnel", None),
            ("ShaderNodeLayerWeight", None),
            ("ShaderNodeRaycast", None),
            ("ShaderNodeTangent", None),
            ("ShaderNodeUVAlongStroke", None),
            ("ShaderNodeUVMap", None),
            ("ShaderNodeWireframe", None),
        )),
        ("Input/Constant", (
            ("FunctionNodeInputBool", None),
            ("ShaderNodeRGB", None),
            ("FunctionNodeInputInt", None),
            ("FunctionNodeInputMenu", None),
            ("ShaderNodeValue", None),
            ("FunctionNodeInputVector", None),
        )),
        ("Output", (
            ("ShaderNodeOutputAOV", None),
            ("ShaderNodeOutputLight", None),
            ("ShaderNodeOutputLineStyle", None),
            ("ShaderNodeOutputMaterial", None),
            ("ShaderNodeOutputWorld", None),
        )),
        ("Shader", (
            ("ShaderNodeAddShader", None),
            ("ShaderNodeMixShader", None),
            ("ShaderNodeBackground", None),
            ("ShaderNodeBsdfDiffuse", None),
            ("ShaderNodeEmission", None),
            ("ShaderNodeBsdfGlass", None),
            ("ShaderNodeBsdfGlossy", None),
            ("ShaderNodeBsdfHair", None),
            ("ShaderNodeHoldout", None),
            ("ShaderNodeBsdfMetallic", None),
            ("ShaderNodeBsdfPrincipled", None),
            ("ShaderNodeBsdfHairPrincipled", None),
            ("ShaderNodeBsdfRayPortal", None),
            ("ShaderNodeBsdfRefraction", None),
            ("ShaderNodeBsdfSheen", None),
            ("ShaderNodeEeveeSpecular", None),
            ("ShaderNodeSubsurfaceScattering", None),
            ("ShaderNodeBsdfToon", None),
            ("ShaderNodeBsdfTranslucent", None),
            ("ShaderNodeBsdfTransparent", None),
            ("ShaderNodeVolumePrincipled", None),
            ("ShaderNodeVolumeAbsorption", None),
            ("ShaderNodeVolumeScatter", None),
            ("ShaderNodeVolumeCoefficients", None),
        )),
        ("Color", (
            ("ShaderNodeBlackbody", None),
            ("ShaderNodeBrightContrast", None),
            ("ShaderNodeValToRGB", None),
            ("ShaderNodeGamma", None),
            ("ShaderNodeHueSaturation", None),
            ("ShaderNodeInvert", None),
            ("ShaderNodeLightFalloff", None),
            ("ShaderNodeRGBCurve", None),
            ("ShaderNodeWavelength", None),
            ("ShaderNodeCombineColor", None),
            ("ShaderNodeSeparateColor", None),
            ("ShaderNodeRGBToBW", None),
            ("ShaderNodeShaderToRGB", None),
        )),
        ("Texture", (
            ("ShaderNodeTexBrick", None),
            ("ShaderNodeTexChecker", None),
            ("ShaderNodeTexEnvironment", None),
            ("ShaderNodeTexGabor", None),
            ("ShaderNodeTexGradient", None),
            ("ShaderNodeTexIES", None),
            ("ShaderNodeTexImage", None),
            ("ShaderNodeTexMagic", None),
            ("ShaderNodeTexNoise", None),
            ("ShaderNodeTexSky", None),
            ("ShaderNodeTexVoronoi", None),
            ("ShaderNodeTexWave", None),
            ("ShaderNodeTexWhiteNoise", None),
        )),
        ("Utilities/Vector", (
            ("ShaderNodeCombineXYZ", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMix", "Mix Vector"),
            ("ShaderNodeSeparateXYZ", None),
            ("ShaderNodeMapping", None),
            ("ShaderNodeNormal", None),
            ("ShaderNodeRadialTiling", None),
            ("ShaderNodeVectorCurve", None),
            ("ShaderNodeVectorMath", None),
            ("ShaderNodeVectorRotate", None),
            ("ShaderNodeVectorTransform", None),
        )),
        ("Utilities/Math", (
            ("ShaderNodeClamp", None),
            ("ShaderNodeFloatCurve", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMath", None),
            ("ShaderNodeMix", None),
        )),
        ("Displacement", (
            ("ShaderNodeBump", None),
            ("ShaderNodeDisplacement", None),
            ("ShaderNodeNormalMap", None),
            ("ShaderNodeVectorDisplacement", None),
        )),
        ("Utilities", (
            ("NodeImplicitConversion", None),
            ("NodeEvaluateClosure", None),
            ("NodeCombineBundle", None),
            ("NodeSeparateBundle", None),
            ("NodeJoinBundle", None),
            ("GeometryNodeMenuSwitch", None),
            ("ShaderNodeScript", None),
        )),
    ),
    "CompositorNodeTree": (
        ("Input", (
            ("CompositorNodeBlankImage", None),
            ("CompositorNodeBokehImage", None),
            ("NodeGroupInput", None),
            ("CompositorNodeImage", None),
            ("CompositorNodeImageInfo", None),
            ("CompositorNodeImageCoordinates", None),
            ("CompositorNodeMask", None),
            ("CompositorNodeMovieClip", None),
            ("CompositorNodeStringToImage", None),
            ("CompositorNodeSequencerStripInfo", None),
        )),
        ("Input/Constant", (
            ("FunctionNodeInputBool", None),
            ("CompositorNodeRGB", None),
            ("GeometryNodeInputFont", None),
            ("FunctionNodeInputInt", None),
            ("FunctionNodeInputIntVector", None),
            ("FunctionNodeInputMenu", None),
            ("CompositorNodeNormal", None),
            ("GeometryNodeInputObject", None),
            ("FunctionNodeInputRotation", None),
            ("FunctionNodeInputString", None),
            ("ShaderNodeValue", None),
            ("FunctionNodeInputVector", None),
        )),
        ("Input/Scene", (
            ("GeometryNodeInputActiveCamera", None),
            ("GeometryNodeCameraInfo", None),
            ("GeometryNodeObjectInfo", None),
            ("CompositorNodeTime", None),
            ("CompositorNodeRLayers", None),
        )),
        ("Output", (
            ("NodeEnableOutput", None),
            ("NodeGroupOutput", None),
            ("CompositorNodeViewer", None),
            ("GeometryNodeWarning", None),
            ("CompositorNodeOutputFile", None),
        )),
        ("Color", (
            ("CompositorNodePremulKey", None),
            ("CompositorNodeAlphaOver", None),
            ("CompositorNodeSetAlpha", None),
            ("CompositorNodeCombineColor", None),
            ("CompositorNodeSeparateColor", None),
            ("CompositorNodeZcombine", None),
            ("ShaderNodeBlackbody", None),
            ("ShaderNodeValToRGB", None),
            ("CompositorNodeConvertColorSpace", None),
            ("CompositorNodeConvertToDisplay", None),
            ("CompositorNodeInvert", None),
            ("CompositorNodeRGBToBW", None),
        )),
        ("Color/Adjust", (
            ("CompositorNodeBrightContrast", None),
            ("CompositorNodeColorBalance", None),
            ("CompositorNodeColorCorrection", None),
            ("CompositorNodeExposure", None),
            ("ShaderNodeGamma", None),
            ("CompositorNodeHueCorrect", None),
            ("CompositorNodeHueSat", None),
            ("CompositorNodeCurveRGB", None),
            ("CompositorNodeTonemap", None),
        )),
        ("Filter", (
            ("CompositorNodeAntiAliasing", None),
            ("CompositorNodeConvolve", None),
            ("CompositorNodeDenoise", None),
            ("CompositorNodeDespeckle", None),
            ("CompositorNodeDilateErode", None),
            ("CompositorNodeMaskToSDF", None),
            ("CompositorNodeInpaint", None),
            ("CompositorNodeFilter", None),
            ("CompositorNodeGlare", None),
        )),
        ("Filter/Blur", (
            ("CompositorNodeBilateralblur", None),
            ("CompositorNodeBlur", None),
            ("CompositorNodeBokehBlur", None),
            ("CompositorNodeDefocus", None),
            ("CompositorNodeDBlur", None),
            ("CompositorNodeVecBlur", None),
        )),
        ("Keying", (
            ("CompositorNodeChannelMatte", None),
            ("CompositorNodeChromaMatte", None),
            ("CompositorNodeColorMatte", None),
            ("CompositorNodeColorSpill", None),
            ("CompositorNodeDiffMatte", None),
            ("CompositorNodeDistanceMatte", None),
            ("CompositorNodeKeying", None),
            ("CompositorNodeKeyingScreen", None),
            ("CompositorNodeLumaMatte", None),
        )),
        ("Mask", (
            ("CompositorNodeCryptomatteV2", None),
            ("CompositorNodeCryptomatte", None),
            ("CompositorNodeBoxMask", None),
            ("CompositorNodeEllipseMask", None),
            ("CompositorNodeDoubleEdgeMask", None),
            ("CompositorNodeIDMask", None),
        )),
        ("Tracking", (
            ("CompositorNodePlaneTrackDeform", None),
            ("CompositorNodeStabilize", None),
            ("CompositorNodeTrackPos", None),
        )),
        ("Transform", (
            ("CompositorNodeRotate", None),
            ("CompositorNodeScale", None),
            ("CompositorNodeTransform", None),
            ("CompositorNodeTranslate", None),
            ("CompositorNodeCornerPin", None),
            ("CompositorNodeCrop", None),
            ("CompositorNodeDisplace", None),
            ("CompositorNodeFlip", None),
            ("CompositorNodeMapUV", None),
            ("CompositorNodeLensdist", None),
            ("CompositorNodeMovieDistortion", None),
        )),
        ("Texture", (
            ("ShaderNodeTexBrick", None),
            ("ShaderNodeTexChecker", None),
            ("ShaderNodeTexGabor", None),
            ("ShaderNodeTexGradient", None),
            ("ShaderNodeTexMagic", None),
            ("ShaderNodeTexNoise", None),
            ("ShaderNodeTexVoronoi", None),
            ("ShaderNodeTexWave", None),
            ("ShaderNodeTexWhiteNoise", None),
        )),
        ("Utilities", (
            ("CompositorNodeLevels", None),
            ("CompositorNodeNormalize", None),
            ("NodeImplicitConversion", None),
            ("CompositorNodeSplit", None),
            ("GeometryNodeSwitch", None),
            ("GeometryNodeIndexSwitch", None),
            ("GeometryNodeMenuSwitch", None),
            ("CompositorNodeSwitchView", "Switch Stereo View"),
            ("CompositorNodeRelativeToPixel", None),
        )),
        ("Utilities/Vector", (
            ("ShaderNodeCombineXYZ", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMix", "Mix Vector"),
            ("ShaderNodeSeparateXYZ", None),
            ("ShaderNodeRadialTiling", None),
            ("ShaderNodeVectorCurve", None),
            ("ShaderNodeVectorMath", None),
            ("ShaderNodeVectorRotate", None),
        )),
        ("Utilities/Math", (
            ("ShaderNodeClamp", None),
            ("ShaderNodeFloatCurve", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMath", None),
            ("ShaderNodeMix", None),
        )),
        ("Utilities/Text", (
            ("FunctionNodeFormatString", None),
            ("FunctionNodeMatchString", None),
            ("FunctionNodeReplaceString", None),
            ("FunctionNodeReverseString", None),
            ("FunctionNodeSetStringCase", None),
            ("FunctionNodeSliceString", None),
            ("FunctionNodeTrimString", None),
            ("FunctionNodeFindInString", None),
            ("FunctionNodeStringLength", None),
            ("FunctionNodeStringToValue", None),
            ("FunctionNodeValueToString", None),
            ("FunctionNodeInputSpecialCharacters", None),
        )),
        ("Utilities/Matrix", (
            ("FunctionNodeCombineMatrix", None),
            ("FunctionNodeMatrixDeterminant", "Determinant"),
            ("FunctionNodeInvertMatrix", None),
            ("FunctionNodeMatrixMultiply", None),
            ("FunctionNodeProjectPoint", None),
            ("FunctionNodeSeparateMatrix", None),
            ("FunctionNodeTransformDirection", None),
            ("FunctionNodeTransformPoint", None),
            ("FunctionNodeTransposeMatrix", None),
        )),
        ("Utilities/Rotation", (
            ("FunctionNodeAlignRotationToVector", None),
            ("FunctionNodeAxesToRotation", None),
            ("FunctionNodeAxisAngleToRotation", None),
            ("FunctionNodeEulerToRotation", None),
            ("FunctionNodeInvertRotation", None),
            ("ShaderNodeMix", "Mix Rotation"),
            ("FunctionNodeRotateRotation", None),
            ("FunctionNodeRotateVector", None),
            ("FunctionNodeRotationToAxisAngle", None),
            ("FunctionNodeRotationToEuler", None),
            ("FunctionNodeRotationToQuaternion", None),
            ("FunctionNodeQuaternionToRotation", None),
        )),
        ("Creative", (
            ("CompositorNodeKuwahara", None),
            ("CompositorNodePixelate", None),
            ("CompositorNodePosterize", None),
        )),
    ),
    "TextureNodeTree": (
        ("Input", (
            ("TextureNodeCoordinates", None),
            ("TextureNodeCurveTime", None),
            ("TextureNodeImage", None),
            ("TextureNodeTexture", None),
        )),
        ("Output", (
            ("TextureNodeOutput", None),
            ("TextureNodeViewer", None),
        )),
        ("Color", (
            ("TextureNodeHueSaturation", None),
            ("TextureNodeInvert", None),
            ("TextureNodeMixRGB", None),
            ("TextureNodeCurveRGB", None),
            ("TextureNodeCombineColor", None),
            ("TextureNodeSeparateColor", None),
        )),
        ("Converter", (
            ("TextureNodeValToRGB", None),
            ("TextureNodeDistance", None),
            ("TextureNodeMath", None),
            ("TextureNodeRGBToBW", None),
            ("TextureNodeValToNor", None),
        )),
        ("Distort", (
            ("TextureNodeAt", None),
            ("TextureNodeRotate", None),
            ("TextureNodeScale", None),
            ("TextureNodeTranslate", None),
        )),
        ("Pattern", (
            ("TextureNodeBricks", None),
            ("TextureNodeChecker", None),
        )),
        ("Texture", (
            ("TextureNodeTexBlend", None),
            ("TextureNodeTexClouds", None),
            ("TextureNodeTexDistNoise", None),
            ("TextureNodeTexMagic", None),
            ("TextureNodeTexMarble", None),
            ("TextureNodeTexMusgrave", None),
            ("TextureNodeTexNoise", None),
            ("TextureNodeTexStucci", None),
            ("TextureNodeTexVoronoi", None),
            ("TextureNodeTexWood", None),
        )),
    ),
    "GeometryNodeTree": (
        ("Attribute", (
            ("GeometryNodeAttributeStatistic", None),
            ("GeometryNodeAttributeDomainSize", None),
            ("GeometryNodeGetAttributeNames", None),
            ("GeometryNodeBlurAttribute", None),
            ("GeometryNodeCaptureAttribute", None),
            ("GeometryNodeRemoveAttribute", None),
            ("GeometryNodeRenameAttribute", None),
            ("GeometryNodeStoreNamedAttribute", None),
            ("GeometryNodeTransferAttributes", None),
        )),
        ("Color", (
            ("ShaderNodeBlackbody", None),
            ("ShaderNodeGamma", None),
            ("ShaderNodeValToRGB", None),
            ("ShaderNodeRGBCurve", None),
            ("FunctionNodeCombineColor", None),
            ("FunctionNodeSeparateColor", None),
        )),
        ("Curve/Read", (
            ("GeometryNodeInputCurveHandlePositions", None),
            ("GeometryNodeCurveLength", None),
            ("GeometryNodeInputTangent", None),
            ("GeometryNodeInputCurveTilt", None),
            ("GeometryNodeCurveEndpointSelection", None),
            ("GeometryNodeCurveHandleTypeSelection", None),
            ("GeometryNodeInputSplineCyclic", None),
            ("GeometryNodeSplineLength", None),
            ("GeometryNodeSplineParameter", None),
            ("GeometryNodeInputSplineResolution", None),
        )),
        ("Curve/Sample", (
            ("GeometryNodeSampleCurve", None),
        )),
        ("Curve/Write", (
            ("GeometryNodeSetCurveNormal", None),
            ("GeometryNodeSetCurveRadius", None),
            ("GeometryNodeSetCurveTilt", None),
            ("GeometryNodeSetCurveHandlePositions", None),
            ("GeometryNodeCurveSetHandles", None),
            ("GeometryNodeSetNURBSOrder", None),
            ("GeometryNodeSetNURBSWeight", None),
            ("GeometryNodeSetSplineCyclic", None),
            ("GeometryNodeSetSplineResolution", None),
            ("GeometryNodeCurveSplineType", None),
        )),
        ("Curve/Operations", (
            ("GeometryNodeCurveToMesh", None),
            ("GeometryNodeCurveToPoints", None),
            ("GeometryNodeCurvesToGreasePencil", None),
            ("GeometryNodeDeformCurvesOnSurface", None),
            ("GeometryNodeFillCurve", None),
            ("GeometryNodeFilletCurve", None),
            ("GeometryNodeInterpolateCurves", None),
            ("GeometryNodeResampleCurve", None),
            ("GeometryNodeReverseCurve", None),
            ("GeometryNodeSubdivideCurve", None),
            ("GeometryNodeTrimCurve", None),
        )),
        ("Curve/Primitives", (
            ("GeometryNodeCurveArc", None),
            ("GeometryNodeCurvePrimitiveBezierSegment", None),
            ("GeometryNodeCurvePrimitiveCircle", None),
            ("GeometryNodeCurvePrimitiveLine", None),
            ("GeometryNodeCurveSpiral", None),
            ("GeometryNodeCurveQuadraticBezier", None),
            ("GeometryNodeCurvePrimitiveQuadrilateral", None),
            ("GeometryNodeCurveStar", None),
        )),
        ("Curve/Topology", (
            ("GeometryNodeCurveOfPoint", None),
            ("GeometryNodeOffsetPointInCurve", None),
            ("GeometryNodePointsOfCurve", None),
        )),
        ("Grease Pencil/Read", (
            ("GeometryNodeInputNamedLayerSelection", None),
        )),
        ("Grease Pencil/Write", (
            ("GeometryNodeSetGreasePencilColor", None),
            ("GeometryNodeSetGreasePencilDepth", None),
            ("GeometryNodeSetGreasePencilSoftness", None),
        )),
        ("Grease Pencil/Operations", (
            ("GeometryNodeGreasePencilToCurves", None),
            ("GeometryNodeMergeLayers", None),
        )),
        ("Geometry", (
            ("GeometryNodeGeometryToInstance", None),
            ("GeometryNodeJoinGeometry", None),
        )),
        ("Geometry/Read", (
            ("GeometryNodeInputID", None),
            ("GeometryNodeInputIndex", None),
            ("GeometryNodeInputNamedAttribute", None),
            ("GeometryNodeInputNormal", None),
            ("GeometryNodeInputPosition", None),
            ("GeometryNodeInputRadius", None),
            ("GeometryNodeGetGeometryBundle", None),
            ("GeometryNodeToolSelection", None),
            ("GeometryNodeToolActiveElement", None),
        )),
        ("Geometry/Write", (
            ("GeometryNodeSetGeometryBundle", None),
            ("GeometryNodeSetGeometryName", None),
            ("GeometryNodeSetID", None),
            ("GeometryNodeSetPosition", None),
            ("GeometryNodeToolSetSelection", None),
        )),
        ("Geometry/Operations", (
            ("GeometryNodeBake", None),
            ("GeometryNodeBoundBox", None),
            ("GeometryNodeConvexHull", None),
            ("GeometryNodeDeleteGeometry", None),
            ("GeometryNodeDuplicateElements", None),
            ("GeometryNodeMergeByDistance", None),
            ("GeometryNodeMergePoints", None),
            ("GeometryNodeSortElements", None),
            ("GeometryNodeTransform", None),
            ("GeometryNodeGetGeometryComponent", None),
            ("GeometryNodeSeparateComponents", None),
            ("GeometryNodeSeparateGeometry", None),
            ("GeometryNodeSplitToInstances", None),
        )),
        ("Geometry/Sample", (
            ("GeometryNodeProximity", None),
            ("GeometryNodeIndexOfNearest", None),
            ("GeometryNodeRaycast", None),
            ("GeometryNodeSampleIndex", None),
            ("GeometryNodeSampleNearest", None),
        )),
        ("Input/Constant", (
            ("FunctionNodeInputBool", None),
            ("GeometryNodeInputCollection", None),
            ("FunctionNodeInputColor", None),
            ("GeometryNodeInputFont", None),
            ("GeometryNodeInputImage", None),
            ("FunctionNodeInputInt", None),
            ("GeometryNodeInputMaterial", None),
            ("FunctionNodeInputMenu", None),
            ("GeometryNodeInputObject", None),
            ("FunctionNodeInputRotation", None),
            ("FunctionNodeInputString", None),
            ("ShaderNodeValue", None),
            ("FunctionNodeInputVector", None),
        )),
        ("Input/Group", (
            ("NodeGroupInput", None),
        )),
        ("Input/Scene", (
            ("GeometryNodeInputActiveCamera", None),
            ("GeometryNodeBoneInfo", None),
            ("GeometryNodeCollectionChildren", None),
            ("GeometryNodeCollectionInfo", None),
            ("GeometryNodeImageInfo", None),
            ("GeometryNodeIsViewport", None),
            ("GeometryNodeObjectInfo", None),
            ("GeometryNodeSelfObject", None),
            ("GeometryNodeTool3DCursor", None),
        )),
        ("Input/Gizmo", (
            ("GeometryNodeGizmoDial", None),
            ("GeometryNodeGizmoLinear", None),
            ("GeometryNodeGizmoTransform", None),
        )),
        ("Instances", (
            ("GeometryNodeInstanceOnPoints", None),
            ("GeometryNodeInstancesToPoints", None),
            ("GeometryNodeRealizeInstances", None),
            ("GeometryNodeRotateInstances", None),
            ("GeometryNodeScaleInstances", None),
            ("GeometryNodeSetInstanceTransform", None),
            ("GeometryNodeTranslateInstances", None),
            ("GeometryNodeInputInstanceBounds", None),
            ("GeometryNodeInputInstanceReference", None),
            ("GeometryNodeInstanceTransform", None),
            ("GeometryNodeInputInstanceRotation", None),
            ("GeometryNodeInputInstanceScale", None),
        )),
        ("Geometry/Material", (
            ("GeometryNodeReplaceMaterial", None),
            ("GeometryNodeInputMaterialIndex", None),
            ("GeometryNodeMaterialSelection", None),
            ("GeometryNodeSetMaterial", None),
            ("GeometryNodeSetMaterialIndex", None),
        )),
        ("Mesh/Read", (
            ("GeometryNodeClusterByConnected", None),
            ("GeometryNodeInputMeshEdgeAngle", None),
            ("GeometryNodeInputMeshEdgeNeighbors", None),
            ("GeometryNodeInputMeshEdgeVertices", None),
            ("GeometryNodeEdgesToFaceGroups", None),
            ("GeometryNodeInputMeshFaceArea", None),
            ("GeometryNodeMeshFaceSetBoundaries", None),
            ("GeometryNodeInputMeshFaceNeighbors", None),
            ("GeometryNodeInputMeshFaceIsPlanar", None),
            ("GeometryNodeInputShadeSmooth", None),
            ("GeometryNodeInputEdgeSmooth", None),
            ("GeometryNodeInputMeshIsland", None),
            ("GeometryNodeInputShortestEdgePaths", None),
            ("GeometryNodeInputMeshVertexNeighbors", None),
            ("GeometryNodeToolFaceSet", None),
        )),
        ("Mesh/Sample", (
            ("GeometryNodeSampleNearestSurface", None),
            ("GeometryNodeSampleUVSurface", None),
        )),
        ("Mesh/Write", (
            ("GeometryNodeSetMeshNormal", None),
            ("GeometryNodeSetShadeSmooth", None),
            ("GeometryNodeToolSetFaceSet", None),
        )),
        ("Mesh/Operations", (
            ("GeometryNodeDualMesh", None),
            ("GeometryNodeEdgePathsToCurves", None),
            ("GeometryNodeEdgePathsToSelection", None),
            ("GeometryNodeExtrudeMesh", None),
            ("GeometryNodeFlipFaces", None),
            ("GeometryNodeMeshBevel", None),
            ("GeometryNodeMeshBoolean", None),
            ("GeometryNodeMeshToCurve", None),
            ("GeometryNodeMeshToDensityGrid", None),
            ("GeometryNodeMeshToPoints", None),
            ("GeometryNodeMeshToSDFGrid", None),
            ("GeometryNodeMeshToVolume", None),
            ("GeometryNodeScaleElements", None),
            ("GeometryNodeSplitEdges", None),
            ("GeometryNodeSubdivideMesh", None),
            ("GeometryNodeSubdivisionSurface", None),
            ("GeometryNodeTriangulate", None),
        )),
        ("Mesh/Primitives", (
            ("GeometryNodeMeshCone", None),
            ("GeometryNodeMeshCube", None),
            ("GeometryNodeMeshCylinder", None),
            ("GeometryNodeMeshGrid", None),
            ("GeometryNodeMeshIcoSphere", None),
            ("GeometryNodeMeshCircle", None),
            ("GeometryNodeMeshLine", None),
            ("GeometryNodeMeshUVSphere", None),
        )),
        ("Input/Import", (
            ("GeometryNodeImportCSV", "CSV (.csv)"),
            ("GeometryNodeImportOBJ", "Wavefront (.obj)"),
            ("GeometryNodeImportPLY", "Stanford PLY (.ply)"),
            ("GeometryNodeImportSTL", "STL (.stl)"),
            ("GeometryNodeImportText", "Text (.txt)"),
            ("GeometryNodeImportVDB", "OpenVDB (.vdb)"),
        )),
        ("Mesh/Topology", (
            ("GeometryNodeCornersOfEdge", None),
            ("GeometryNodeCornersOfFace", None),
            ("GeometryNodeCornersOfVertex", None),
            ("GeometryNodeEdgesOfCorner", None),
            ("GeometryNodeEdgesOfVertex", None),
            ("GeometryNodeFaceOfCorner", None),
            ("GeometryNodeOffsetCornerInFace", None),
            ("GeometryNodeVertexOfCorner", None),
        )),
        ("Output", (
            ("NodeEnableOutput", None),
            ("NodeGroupOutput", None),
            ("GeometryNodeViewer", None),
            ("GeometryNodeWarning", None),
        )),
        ("Point", (
            ("GeometryNodeDistributePointsInGrid", None),
            ("GeometryNodeDistributePointsInVolume", None),
            ("GeometryNodeDistributePointsOnFaces", None),
            ("GeometryNodePoints", None),
            ("GeometryNodePointsToCurves", None),
            ("GeometryNodePointsToSDFGrid", None),
            ("GeometryNodePointsToVertices", None),
            ("GeometryNodePointsToVolume", None),
            ("GeometryNodeSetPointRadius", None),
        )),
        ("Simulation", (
            ("GeometryNodeXPBDSolver", None),
        )),
        ("Utilities/Text", (
            ("FunctionNodeFormatString", None),
            ("GeometryNodeStringJoin", None),
            ("FunctionNodeMatchString", None),
            ("FunctionNodeReplaceString", None),
            ("FunctionNodeReverseString", None),
            ("FunctionNodeSliceString", None),
            ("FunctionNodeSetStringCase", None),
            ("FunctionNodeSplitString", None),
            ("FunctionNodeTrimString", None),
            ("FunctionNodeFindInString", None),
            ("FunctionNodeStringLength", None),
            ("GeometryNodeStringToCurves", None),
            ("FunctionNodeStringToValue", None),
            ("FunctionNodeValueToString", None),
            ("FunctionNodeInputSpecialCharacters", None),
            ("GeometryNodeTagFilter", None),
        )),
        ("Utilities/Sound", (
            ("GeometryNodeSampleSoundFrequencies", None),
        )),
        ("Texture", (
            ("ShaderNodeTexBrick", None),
            ("ShaderNodeTexChecker", None),
            ("ShaderNodeTexGabor", None),
            ("ShaderNodeTexGradient", None),
            ("GeometryNodeImageTexture", None),
            ("ShaderNodeTexMagic", None),
            ("ShaderNodeTexNoise", None),
            ("ShaderNodeTexVoronoi", None),
            ("ShaderNodeTexWave", None),
            ("ShaderNodeTexWhiteNoise", None),
        )),
        ("Utilities", (
            ("NodeImplicitConversion", None),
            ("GeometryNodeIndexSwitch", None),
            ("GeometryNodeMenuSwitch", None),
            ("FunctionNodeRandomValue", None),
            ("GeometryNodeSwitch", None),
        )),
        ("Utilities/Deprecated", (
            ("FunctionNodeAlignEulerToVector", None),
            ("FunctionNodeRotateEuler", None),
        )),
        ("Utilities/Field", (
            ("GeometryNodeAccumulateField", None),
            ("GeometryNodeClusterByDistance", None),
            ("GeometryNodeFieldAtIndex", None),
            ("GeometryNodeFieldOnDomain", None),
            ("GeometryNodeFieldAverage", None),
            ("GeometryNodeFieldMinAndMax", None),
            ("GeometryNodeFieldVariance", None),
        )),
        ("Utilities/Rotation", (
            ("FunctionNodeAlignRotationToVector", None),
            ("FunctionNodeAxesToRotation", None),
            ("FunctionNodeAxisAngleToRotation", None),
            ("FunctionNodeEulerToRotation", None),
            ("FunctionNodeInvertRotation", None),
            ("ShaderNodeMix", "Mix Rotation"),
            ("FunctionNodeRotateRotation", None),
            ("FunctionNodeRotateVector", None),
            ("FunctionNodeRotationToAxisAngle", None),
            ("FunctionNodeRotationToEuler", None),
            ("FunctionNodeRotationToQuaternion", None),
            ("FunctionNodeQuaternionToRotation", None),
        )),
        ("Utilities/Matrix", (
            ("FunctionNodeCombineMatrix", None),
            ("FunctionNodeCombineTransform", None),
            ("FunctionNodeMatrixDeterminant", "Determinant"),
            ("FunctionNodeInvertMatrix", None),
            ("FunctionNodeMatrixMultiply", None),
            ("FunctionNodeMatrixSVD", None),
            ("FunctionNodeProjectPoint", None),
            ("FunctionNodeSeparateMatrix", None),
            ("FunctionNodeSeparateTransform", None),
            ("FunctionNodeTransformDirection", None),
            ("FunctionNodeTransformPoint", None),
            ("FunctionNodeTransposeMatrix", None),
        )),
        ("Utilities/Bundle", (
            ("NodeCombineBundle", None),
            ("NodeSeparateBundle", None),
            ("NodeGetBundleItem", None),
            ("NodeGetNestedBundlePaths", None),
            ("NodeStoreBundleItem", None),
            ("NodeJoinBundle", None),
        )),
        ("Utilities/Closure", (
            ("NodeEvaluateClosure", None),
        )),
        ("Utilities/List", (
            ("GeometryNodeClosureToList", None),
            ("GeometryNodeFieldToList", None),
            ("GeometryNodeFilterList", None),
            ("GeometryNodeListGetItem", None),
            ("GeometryNodeListLength", None),
            ("GeometryNodeSortList", None),
        )),
        ("Utilities/Math", (
            ("FunctionNodeBitMath", None),
            ("FunctionNodeBooleanMath", None),
            ("FunctionNodeIntegerMath", None),
            ("ShaderNodeClamp", None),
            ("FunctionNodeCompare", None),
            ("ShaderNodeFloatCurve", None),
            ("FunctionNodeFloatToInt", None),
            ("FunctionNodeHashValue", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMath", None),
            ("ShaderNodeMix", None),
        )),
        ("Mesh/UV", (
            ("GeometryNodeUVPackIslands", None),
            ("GeometryNodeUVTangent", None),
            ("GeometryNodeUVUnwrap", None),
        )),
        ("Utilities/Vector", (
            ("ShaderNodeCombineXYZ", None),
            ("ShaderNodeMapRange", None),
            ("ShaderNodeMix", "Mix Vector"),
            ("ShaderNodeSeparateXYZ", None),
            ("ShaderNodeRadialTiling", None),
            ("ShaderNodeVectorCurve", None),
            ("ShaderNodeVectorMath", None),
            ("ShaderNodeVectorRotate", None),
        )),
        ("Volume/Read", (
            ("GeometryNodeGetNamedGrid", None),
            ("GeometryNodeGridInfo", None),
            ("GeometryNodeInputVoxelIndex", None),
        )),
        ("Volume/Write", (
            ("GeometryNodeSetGridBackground", None),
            ("GeometryNodeSetGridTransform", None),
            ("GeometryNodeStoreNamedGrid", None),
        )),
        ("Volume/Sample", (
            ("GeometryNodeSampleGrid", None),
            ("GeometryNodeSampleGridIndex", None),
            ("GeometryNodeGridAdvect", None),
            ("GeometryNodeGridCurl", None),
            ("GeometryNodeGridDivergence", None),
            ("GeometryNodeGridGradient", None),
            ("GeometryNodeGridLaplacian", None),
        )),
        ("Volume/Operations", (
            ("GeometryNodeGridToMesh", None),
            ("GeometryNodeGridToPoints", None),
            ("GeometryNodeVolumeToMesh", None),
            ("GeometryNodeSDFGridBoolean", None),
            ("GeometryNodeSDFGridFillet", None),
            ("GeometryNodeSDFGridLaplacian", None),
            ("GeometryNodeSDFGridMean", None),
            ("GeometryNodeSDFGridMeanCurvature", None),
            ("GeometryNodeSDFGridMedian", None),
            ("GeometryNodeSDFGridOffset", None),
            ("GeometryNodeFieldToGrid", None),
            ("GeometryNodeGridClip", None),
            ("GeometryNodeGridDilateAndErode", None),
            ("GeometryNodeGridMean", None),
            ("GeometryNodeGridMedian", None),
            ("GeometryNodeGridPrune", None),
            ("GeometryNodeGridVoxelize", None),
        )),
        ("Volume/Primitives", (
            ("GeometryNodeCubeGridTopology", None),
            ("GeometryNodeVolumeCube", None),
        )),
    ),
}
# === END GENERATED NODE TABLE ===

# 少数分类名在词条里不够准确，这里覆盖（其余分类名都查 Blender 自带翻译）
NODE_CATEGORY_ZH = {
    "Group": "组",
    "Linked": "已链接",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _prefs(context=None):
    context = context or bpy.context
    try:
        return context.preferences.addons[__name__].preferences
    except (KeyError, AttributeError, TypeError):
        return None


def _alias_menu_text(prefs):
    """别名子菜单的按钮文本 —— 它会成为搜索结果里的前缀。

    Blender 的搜索路径是按「按钮文本 ‣ 子菜单 ‣ 条目」拼出来的，
    所以这里用短前缀（默认 BNA）能让搜索结果更紧凑。
    """
    prefix = ""
    if prefs is not None:
        prefix = str(getattr(prefs, "alias_prefix", "") or "")
    return prefix.strip() or DEFAULT_ALIAS_PREFIX


def _draw_alias_submenu(layout, menu_idname, prefs, enabled):
    """在原生「添加」菜单末尾加一行分隔线 + 别名子菜单按钮（文本即搜索前缀）。"""
    if not enabled:
        return
    layout.separator()
    layout.menu(menu_idname, text=_alias_menu_text(prefs), icon='VIEWZOOM')


def _valid_icon_names():
    """UILayout.operator 支持的图标标识符集合（用于剔除失效图标）。"""
    try:
        props = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"]
        return {item.identifier for item in props.enum_items}
    except Exception:
        return None


def _bilingual_label(zh, en):
    if zh and en and zh != en:
        return "%s %s" % (zh, en)
    return en or zh


def validate_alias_data():
    """校验别名表：算子是否存在、属性与枚举值是否合法、图标是否可用。

    返回 (可用分类, 被丢弃条目说明)。这样即使将来 Blender 改名，插件也只是
    少几个别名，而不会在点击时抛异常。
    """
    valid_icons = _valid_icon_names()
    kept_categories = []
    dropped = []
    for (cat_zh, cat_en, cat_icon, context_name, items) in ALIAS_CATEGORIES:
        kept_items = []
        for (zh, en, op_id, props, icon) in items:
            try:
                module_name, op_name = op_id.split(".", 1)
                rna = getattr(getattr(bpy.ops, module_name), op_name).get_rna_type()
            except Exception:
                dropped.append("%s (%s): operator not found" % (en, op_id))
                continue
            bad_prop = None
            for key, value in (props or {}).items():
                try:
                    prop = rna.properties[key]
                except Exception:
                    bad_prop = "no property %r" % key
                    break
                if prop.type == 'ENUM':
                    identifiers = {i.identifier for i in prop.enum_items}
                    if value not in identifiers:
                        bad_prop = "%r not in %s" % (value, sorted(identifiers))
                        break
                elif prop.type == 'BOOLEAN':
                    if not isinstance(value, bool):
                        bad_prop = "%r is not a bool" % (value,)
                        break
            if bad_prop is not None:
                dropped.append("%s (%s): %s" % (en, op_id, bad_prop))
                continue
            if valid_icons is not None and icon not in valid_icons:
                icon = 'DOT'
            kept_items.append((zh, en, op_id, props, icon))
        if kept_items:
            if valid_icons is not None and cat_icon not in valid_icons:
                cat_icon = 'DOT'
            kept_categories.append((cat_zh, cat_en, cat_icon, context_name, tuple(kept_items)))
    return tuple(kept_categories), dropped


# ---------------------------------------------------------------------------
# 菜单
# ---------------------------------------------------------------------------

_alias_categories = ()
_category_menu_classes = []


def _make_category_menu(index, category):
    cat_zh, cat_en, cat_icon, context_name, items = category

    def draw(self, _context):
        layout = self.layout
        layout.operator_context = context_name
        for (zh, en, op_id, props, icon) in items:
            try:
                button = layout.operator(op_id, text=_bilingual_label(zh, en), icon=icon)
            except Exception:
                continue
            for key, value in (props or {}).items():
                try:
                    setattr(button, key, value)
                except Exception:
                    pass

    return type(
        "BILINGUAL_MT_add_alias_%02d" % index,
        (Menu,),
        {
            "bl_idname": "BILINGUAL_MT_add_alias_%02d" % index,
            "bl_label": _bilingual_label(cat_zh, cat_en),
            "bl_options": {'SEARCH_ON_KEY_PRESS'},
            "draw": draw,
        },
    )


class BILINGUAL_MT_add_aliases(Menu):
    bl_idname = ROOT_MENU_IDNAME
    # 搜索结果的前缀就是这个标签（菜单按钮文本优先，这里兜底），所以保持短
    bl_label = DEFAULT_ALIAS_PREFIX
    bl_options = {'SEARCH_ON_KEY_PRESS'}

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        for cls in _category_menu_classes:
            layout.menu(cls.bl_idname)
        prefs = _prefs(context)
        if prefs is None or prefs.show_language_toggle:
            layout.separator()
            layout.operator(TOGGLE_OPERATOR_IDNAME, icon='FILE_REFRESH')


def _draw_add_menu_entry(self, context):
    """把别名子菜单挂到 3D 视图的「添加」菜单（Shift+A）末尾。"""
    prefs = _prefs(context)
    _draw_alias_submenu(
        self.layout,
        ROOT_MENU_IDNAME,
        prefs,
        prefs is None or prefs.show_aliases,
    )


# ---------------------------------------------------------------------------
# 节点菜单（材质/合成/几何/纹理 节点编辑器）
# ---------------------------------------------------------------------------

_node_roots = {}
_node_menu_classes = []
_node_label_cache = {}
_translation_catalog = None


def _ensure_catalog():
    """加载 Blender 自带的 zh 翻译词条，用于把节点英文名换成官方中文名。"""
    global _translation_catalog
    if _translation_catalog is not None:
        return _translation_catalog

    import gettext
    import os

    languages = []
    try:
        current = bpy.context.preferences.view.language
    except Exception:
        current = None
    if current and str(current).upper().startswith("ZH"):
        languages.append(current)
    languages.extend(("zh_HANS", "zh_HANT"))

    locale_root = os.path.join(bpy.utils.resource_path('LOCAL'), "datafiles", "locale")
    for language in languages:
        try:
            catalog = gettext.translation(
                "blender", localedir=locale_root, languages=[language]
            )._catalog
        except Exception:
            continue
        if catalog:
            _translation_catalog = catalog
            return _translation_catalog

    _translation_catalog = {}
    return _translation_catalog


def _catalog_lookup(message, context=None):
    catalog = _ensure_catalog()
    if context and context != "*":
        value = catalog.get("%s\x04%s" % (context, message))
        if value:
            return value
    value = catalog.get(message)
    if value:
        return value
    for key, val in catalog.items():
        if isinstance(key, str) and val and key.endswith("\x04" + message):
            return val
    return ""


def _node_labels():
    """节点标签缓存: (节点 ID, 标签覆盖) -> (中文, 英文)。"""
    if _node_label_cache:
        return _node_label_cache
    for groups in NODE_ALIAS_GROUPS.values():
        for _path, items in groups:
            for idname, override in items:
                key = (idname, override)
                if key in _node_label_cache:
                    continue
                rna = bpy.types.Node.bl_rna_get_subclass(idname)
                if rna is None:
                    continue
                translation_context = getattr(rna, "translation_context", None)
                english = override or rna.name
                chinese = _catalog_lookup(english, translation_context)
                if not chinese and override:
                    chinese = _catalog_lookup(rna.name, translation_context)
                _node_label_cache[key] = (chinese, english)
    return _node_label_cache


def _category_label(components):
    english = components[-1]
    chinese = NODE_CATEGORY_ZH.get(english) or _catalog_lookup(english)
    return _bilingual_label(chinese, english)


def _make_node_menu_class(index, components, items, children):
    def draw(self, _context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        labels = _node_labels()
        for idname, override in items:
            chinese, english = labels.get((idname, override), ("", override or idname))
            try:
                props = layout.operator(
                    NODE_ADD_OPERATOR_IDNAME,
                    text=_bilingual_label(chinese, english),
                    icon='NODE',
                )
                props.type = idname
                if hasattr(props, "use_transform"):
                    props.use_transform = True
            except Exception:
                continue
        if children:
            layout.separator()
            for child in children:
                layout.menu(child.bl_idname, text=_category_label(child.alias_components))

    return type(
        "BILINGUAL_MT_node_%03d" % index,
        (Menu,),
        {
            "bl_idname": "BILINGUAL_MT_node_%03d" % index,
            "bl_label": components[-1],
            "bl_options": {'SEARCH_ON_KEY_PRESS'},
            "alias_components": components,
            "alias_children": tuple(children),
            "draw": draw,
        },
    )


def _build_node_menus():
    """按树类型生成分类菜单类；返回 (根菜单表, 菜单类, 失效节点列表)。"""
    roots = {}
    classes = []
    dropped = []
    counter = [0]

    def build(components, node):
        children = tuple(
            build(components + (name,), child) for name, child in node["children"].items()
        )
        if not node["items"] and len(children) == 1:
            return children[0]
        counter[0] += 1
        cls = _make_node_menu_class(counter[0], components, tuple(node["items"]), children)
        classes.append(cls)
        return cls

    for tree_type, groups in NODE_ALIAS_GROUPS.items():
        validated = []
        for path, items in groups:
            kept = []
            for idname, override in items:
                if bpy.types.Node.bl_rna_get_subclass(idname) is None:
                    dropped.append(idname)
                else:
                    kept.append((idname, override))
            if kept:
                validated.append((path, tuple(kept)))

        tree = {"items": [], "children": {}}
        for path, items in validated:
            node = tree
            for component in path.split("/"):
                node = node["children"].setdefault(component, {"items": [], "children": {}})
            node["items"].extend(items)

        roots[tree_type] = tuple(
            build((name,), child) for name, child in tree["children"].items()
        )

    return roots, classes, dropped


class BILINGUAL_MT_node_aliases(Menu):
    bl_idname = NODE_ROOT_MENU_IDNAME
    # 同上：作为搜索结果前缀的兜底标签
    bl_label = DEFAULT_ALIAS_PREFIX
    bl_options = {'SEARCH_ON_KEY_PRESS'}

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        space_data = getattr(context, "space_data", None)
        tree_type = getattr(space_data, "tree_type", None)
        root_menus = _node_roots.get(tree_type)
        if not root_menus:
            layout.label(text="当前节点树没有双语别名 / no aliases for this tree", icon='INFO')
            return
        for child in root_menus:
            layout.menu(child.bl_idname, text=_category_label(child.alias_components))


def _draw_node_menu_entry(self, context):
    """把节点别名子菜单挂到节点编辑器的「添加」菜单（Shift+A）末尾。"""
    prefs = _prefs(context)
    _draw_alias_submenu(
        self.layout,
        NODE_ROOT_MENU_IDNAME,
        prefs,
        prefs is None or prefs.show_node_aliases,
    )


# ---------------------------------------------------------------------------
# 一键切换界面语言
# ---------------------------------------------------------------------------

class BILINGUAL_OT_toggle_ui_language(Operator):
    bl_idname = TOGGLE_OPERATOR_IDNAME
    bl_label = "切换界面语言 中文/English"
    bl_description = "在两种界面语言之间快速切换（默认 简体中文 ⇄ English）"
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = _prefs(context)
        view = context.preferences.view
        lang_a = getattr(prefs, "lang_a", None) or 'zh_HANS'
        lang_b = getattr(prefs, "lang_b", None) or 'en_US'
        current = view.language

        if current == lang_a:
            target = lang_b
        elif current == lang_b:
            target = lang_a
        elif str(current).upper().startswith("ZH"):
            target = lang_b
        else:
            target = lang_a

        try:
            view.language = target
        except TypeError:
            self.report({'ERROR'}, "不支持的语言代码: %s" % target)
            return {'CANCELLED'}

        if prefs is not None and prefs.save_preferences:
            try:
                bpy.ops.wm.save_userpref()
            except Exception:
                pass

        self.report({'INFO'}, "界面语言 → %s" % target)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 偏好设置
# ---------------------------------------------------------------------------

def _default_chinese_locale():
    locales = set(getattr(bpy.app.translations, "locales", ()) or ())
    for candidate in ('zh_HANS', 'zh_CN', 'zh_HANT', 'zh_TW'):
        if candidate in locales:
            return candidate
    return 'zh_HANS'


def _language_items():
    """界面语言枚举项（静态列表，字符串默认值要求 items 不是回调）。"""
    locales = [loc for loc in (getattr(bpy.app.translations, "locales", ()) or ())]
    if not locales:
        locales = ['en_US', 'zh_HANS', 'zh_HANT']
    for fallback in (_default_chinese_locale(), 'en_US'):
        if fallback not in locales:
            locales.append(fallback)
    return [(loc, loc, "") for loc in locales]


_LANGUAGE_ITEMS = _language_items()


class BilingualAddSearchPreferences(AddonPreferences):
    bl_idname = __name__

    show_aliases: BoolProperty(
        name="在「添加」菜单中显示双语别名",
        description="在 Shift+A 的添加菜单末尾附加中英双语别名子菜单（搜索框可中英文搜索）",
        default=True,
    )
    show_node_aliases: BoolProperty(
        name="在节点「添加」菜单中显示双语别名",
        description="在节点编辑器 Shift+A 的添加菜单末尾附加中英双语节点别名（材质/合成/几何/纹理节点）",
        default=True,
    )
    show_language_toggle: BoolProperty(
        name="别名菜单中显示语言切换按钮",
        default=True,
    )
    alias_prefix: StringProperty(
        name="搜索前缀",
        description="别名菜单的按钮文本，也是搜索结果里的前缀（例如 BNA ‣ 着色器 Shader ‣ 混合着色器 Mix Shader）",
        default=DEFAULT_ALIAS_PREFIX,
    )
    enable_hotkey: BoolProperty(
        name="启用语言切换快捷键 Shift+Alt+L",
        description="在任意窗口按下 Shift+Alt+L 即可切换界面语言",
        default=True,
        update=lambda self, context: _sync_hotkey(),
    )
    lang_a: EnumProperty(
        name="语言 A",
        items=_LANGUAGE_ITEMS,
        default=_default_chinese_locale(),
    )
    lang_b: EnumProperty(
        name="语言 B",
        items=_LANGUAGE_ITEMS,
        default='en_US',
    )
    save_preferences: BoolProperty(
        name="切换语言后立即保存用户设置",
        description="关闭时仅本次会话生效（是否保留取决于 Blender 的自动保存偏好设置）",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        column.prop(self, "show_aliases")
        column.prop(self, "show_node_aliases")
        column.prop(self, "show_language_toggle")
        column.prop(self, "enable_hotkey")

        row = layout.row(align=True)
        row.prop(self, "lang_a")
        row.prop(self, "lang_b")
        layout.prop(self, "save_preferences")

        box = layout.box()
        box.label(text="搜索结果前缀 / Search prefix:", icon='SORT_ASC')
        box.prop(self, "alias_prefix")

        layout.operator(TOGGLE_OPERATOR_IDNAME, icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="用法 / Usage:", icon='INFO')
        box.label(text="3D 视图 Shift+A → 输入 cube 或 立方体，都能命中同一条目")
        box.label(text="材质节点 Shift+A → 输入 noise 或 噪波纹理，都能命中同一节点")
        box.label(text="语言切换：Shift+Alt+L 或上面的按钮")


# ---------------------------------------------------------------------------
# 快捷键
# ---------------------------------------------------------------------------

def _add_hotkey():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    keyconfig = wm.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.get("Window")
    if keymap is None:
        keymap = keyconfig.keymaps.new(name="Window", space_type='EMPTY')
    for item in keymap.keymap_items:
        if item.idname == TOGGLE_OPERATOR_IDNAME:
            item.active = True
            return
    keymap.keymap_items.new(TOGGLE_OPERATOR_IDNAME, **DEFAULT_HOTKEY)


def _remove_hotkey():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    keyconfig = wm.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.get("Window")
    if keymap is None:
        return
    for item in list(keymap.keymap_items):
        if item.idname == TOGGLE_OPERATOR_IDNAME:
            keymap.keymap_items.remove(item)


def _sync_hotkey():
    prefs = _prefs()
    _remove_hotkey()
    if prefs is None or prefs.enable_hotkey:
        _add_hotkey()


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

_classes = []


def register():
    global _alias_categories, _category_menu_classes, _classes
    global _node_roots, _node_menu_classes, _node_label_cache, _translation_catalog

    _alias_categories, dropped = validate_alias_data()
    if dropped:
        print("[Bilingual Add Search] 跳过 %d 个失效别名: %s" % (len(dropped), "; ".join(dropped)))

    _category_menu_classes = [
        _make_category_menu(index, category)
        for index, category in enumerate(_alias_categories)
    ]

    _node_label_cache = {}
    _translation_catalog = None
    _node_roots, _node_menu_classes, node_dropped = _build_node_menus()
    if node_dropped:
        print("[Bilingual Add Search] 跳过 %d 个失效节点别名: %s"
              % (len(node_dropped), ", ".join(sorted(set(node_dropped)))))

    _classes = [BilingualAddSearchPreferences, BILINGUAL_OT_toggle_ui_language] + \
        _category_menu_classes + [BILINGUAL_MT_add_aliases] + \
        _node_menu_classes + [BILINGUAL_MT_node_aliases]
    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_add.append(_draw_add_menu_entry)
    if hasattr(bpy.types, "NODE_MT_add"):
        bpy.types.NODE_MT_add.append(_draw_node_menu_entry)
    _add_hotkey()


def unregister():
    global _category_menu_classes, _classes, _node_menu_classes, _node_roots

    _remove_hotkey()
    try:
        bpy.types.VIEW3D_MT_add.remove(_draw_add_menu_entry)
    except Exception:
        pass
    if hasattr(bpy.types, "NODE_MT_add"):
        try:
            bpy.types.NODE_MT_add.remove(_draw_node_menu_entry)
        except Exception:
            pass
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _classes = []
    _category_menu_classes = []
    _node_menu_classes = []
    _node_roots = {}


if __name__ == "__main__":
    register()
