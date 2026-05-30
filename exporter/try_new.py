import bpy
import random
import os
import numpy as np
import sys
from bpy_extras.io_utils import axis_conversion

# 假设 SceneConverter 已经在正确的位置
sys.path.append(r"D:\科研资料\scene_object\mitsuba-blender\io\exporter")
from convert import SceneConverter 

# 导出 Mitsuba 场景的函数
def export_mitsuba(filepath, use_selection=False, split_files=False, export_ids=True, ignore_background=True, axis_forward='Y', axis_up='Z'):
    print("开始导出 Mitsuba 场景...")

    # 初始化转换器
    converter = SceneConverter(render=False)
    converter.use_selection = use_selection
    converter.ignore_background = ignore_background

    # 设置坐标轴转换矩阵
    axis_mat = axis_conversion(to_forward=axis_forward, to_up=axis_up).to_4x4()
    converter.export_ctx.axis_mat = axis_mat
    converter.export_ctx.export_ids = export_ids

    # 设置导出路径和子文件选项
    converter.set_path(filepath, split_files=split_files)

    # 获取 Blender 当前场景依赖图
    deps_graph = bpy.context.evaluated_depsgraph_get()
    wm = bpy.context.window_manager

    # 显示进度条
    wm.progress_begin(0, len(deps_graph.object_instances))

    # 执行导出
    converter.scene_to_dict(deps_graph, wm)
    converter.dict_to_xml()

    wm.progress_end()
    print(f"✅ 导出完成：{filepath}")

# 配置参数
PLANE_SIZE = 32       # 平面尺寸
CELL_SIZE = 4         # 单元尺寸
BUILDING_WIDTH = 3    # 随机建筑宽度
BUILDING_DEPTH = 3     # 随机建筑深度
BUILDING_HEIGHT_NORMAL = 6  # 正常建筑高度
BUILDING_HEIGHT_TALL = 12    # 高建筑高度
BASE_STATION_WIDTH = 3  # 基站建筑宽度
BASE_STATION_DEPTH = 3   # 基站建筑深度

# 概率控制选项
SPAWN_PROBABILITY = 0.2  # 生成概率 (0.0-1.0)
SCENE_COUNT = 50         # 场景数量（可自定义）

# 保存路径
OUTPUT_DIR = "D:\\科研资料\\scene_object\\\\output32\\"  # 更改为您的输出目录

# 创建材质函数
def create_material():
    material_name = "itu_concrete"
    material = bpy.data.materials.get(material_name)
    if material is None:  # 检查材质是否已存在
        material = bpy.data.materials.new(name=material_name)
        material.diffuse_color = (0.8, 0.6, 0.4, 1)  # 设置颜色
    return material

def create_building(i, j, height, material, width, depth):
    x = (i * CELL_SIZE) + CELL_SIZE / 2 - PLANE_SIZE / 2
    y = (j * CELL_SIZE) + CELL_SIZE / 2 - PLANE_SIZE / 2

    # 创建建筑
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, height / 2), scale=(width, depth, height))
    building = bpy.context.active_object
    building.name = f"Building_{i}_{j}"
    
    # 添加材质到建筑
    if len(building.data.materials) == 0:
        building.data.materials.append(material)
    else:
        building.data.materials[0] = material

    return building

# 主程序
def main():
    # 清除场景中已有对象
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # 创建基础平面
    bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Base_Plane"

    # 创建材质
    material = create_material()
    plane.data.materials.append(material)  # 将材质应用到基础平面

    # 检查并创建输出目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 计算网格参数
    grid_count = PLANE_SIZE // CELL_SIZE  # 8x8 网格

    # 放置基站的位置（四个角和中间四个单元）
    fixed_cells = {
        (0, 0)# 左下角
    }

    # 禁止生成建筑的单元格
    forbidden_cells = {
    }

    # 生成建筑物
    for scene_index in range(SCENE_COUNT):
        # 每次生成新场景前清空场景并创建基础设施
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
        plane = bpy.context.active_object
        plane.name = "Base_Plane"
        plane.data.materials.append(material)  # 将材质应用到基础平面

        # 重新初始化掩码矩阵
        matrix_mask = np.zeros((grid_count, grid_count), dtype=int)  # 创建0,1掩码矩阵

        # 生成建筑
        for i in range(grid_count):
            for j in range(grid_count):
                if (i, j) in forbidden_cells:
                    continue  # 跳过禁止的单元
                if (i, j) in fixed_cells:  # 生成固定建筑
                    height = BUILDING_HEIGHT_TALL if (i, j) in fixed_cells else BUILDING_HEIGHT_NORMAL
                    create_building(i, j, height, material, BUILDING_WIDTH, BUILDING_DEPTH)
                    
                    # 计算对称位置的索引
                    symmetric_i = grid_count - 1 - i
                    symmetric_j = grid_count - 1 - j
                    matrix_mask[symmetric_i][symmetric_j] = 2  # 记录掩码
                    
                elif random.random() <= SPAWN_PROBABILITY:  # 随机生成建筑
                    height = BUILDING_HEIGHT_NORMAL
                    create_building(i, j, height, material, BUILDING_WIDTH, BUILDING_DEPTH)  # 建筑物尺寸调整为 24x24

                    # 计算对称位置的索引
                    symmetric_i = grid_count - 1 - i
                    symmetric_j = grid_count - 1 - j
                    matrix_mask[symmetric_i][symmetric_j] = 1  # 记录掩码

        # 为当前场景创建新文件夹
        scene_output_dir = os.path.join(OUTPUT_DIR, f"scene_{scene_index}")
        if not os.path.exists(scene_output_dir):
            os.makedirs(scene_output_dir)

        # 保存掩码矩阵为CSV格式
        np.savetxt(os.path.join(scene_output_dir, f"mask_{scene_index}.csv"), matrix_mask, delimiter=',', fmt='%d')
        export_mitsuba(filepath=os.path.join(scene_output_dir, f"scene_{scene_index}.xml"))

    print(f"所有场景生成完成!")

if __name__ == "__main__":
    main()
