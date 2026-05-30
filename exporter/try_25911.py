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
def export_mitsuba(
    filepath,
    use_selection=False,
    split_files=False,
    export_ids=True,
    ignore_background=True,
    axis_forward='Y',
    axis_up='Z'):
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

# 配置参数#########dont forget' at least number' setup
PLANE_SIZE = 64       # 平面尺寸
CELL_SIZE = 8         # 单元尺寸

BUILDING_WIDTH = 6    # 随机建筑宽度
BUILDING_DEPTH = 6    # 随机建筑深度
BUILDING_HEIGHT_NORMAL = 6  # 正常建筑高度
BUILDING_HEIGHT_TALL = 12    # 高建筑高度

BASE_STATION_WIDTH = 6  # 基站建筑宽度
BASE_STATION_DEPTH = 6  # 基站建筑深度

# 概率控制选项
SPAWN_PROBABILITY = 0.2  # 生成概率 (0.0-1.0)
SCENE_COUNT = 1          # 场景数量（可自定义）

# 保存路径
OUTPUT_DIR = "D:\\科研资料\\scene_object\\output64\\"  # 更改为您的输出目录

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

    # 生成建筑物
    for scene_index in range(1, 1 + SCENE_COUNT):
        # 每次生成新场景前清空场景并创建基础设施
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
        plane = bpy.context.active_object
        plane.name = "Base_Plane"
        plane.data.materials.append(material)

        # 初始化掩码矩阵
        matrix_mask = np.zeros((grid_count, grid_count), dtype=int)

        # 存储生成的建筑位置和类型（True=基站，False=普通）
        generated_positions = []  # [(i, j), ...]

        # 第一步：按概率生成所有建筑（忽略 forbidden_cells，全部64格参与）
        for i in range(grid_count):
            for j in range(grid_count):
                if random.random() <= SPAWN_PROBABILITY:
                    generated_positions.append((i, j))

        # 检查是否至少生成了8个建筑
        if len(generated_positions) < 8:
            raise ValueError(
                f"场景 {scene_index} 中只生成了 {len(generated_positions)} 个建筑，"
                f"少于要求的 8 个基站建筑！请提高 SPAWN_PROBABILITY 或手动处理。"
            )

        # 第二步：从中随机抽取8个作为基站建筑
        base_station_positions = set(random.sample(generated_positions, 1))
        # 其余为普通建筑
        normal_positions = [pos for pos in generated_positions if pos not in base_station_positions]

        # 第三步：实际创建建筑 + 设置掩码
        for pos in generated_positions:
            i, j = pos
            if pos in base_station_positions:
                # 创建基站建筑
                create_building(i, j, BUILDING_HEIGHT_TALL, material, BASE_STATION_WIDTH, BASE_STATION_DEPTH)
                mark_value = 2
            else:
                # 创建普通建筑
                create_building(i, j, BUILDING_HEIGHT_NORMAL, material, BUILDING_WIDTH, BUILDING_DEPTH)
                mark_value = 1

            # 计算对称位置（保持你原有逻辑）
            symmetric_i = grid_count - 1 - i
            symmetric_j = grid_count - 1 - j
            matrix_mask[symmetric_i][symmetric_j] = mark_value

        # 为当前场景创建新文件夹
        scene_output_dir = os.path.join(OUTPUT_DIR, f"scene_{scene_index}")
        if not os.path.exists(scene_output_dir):
            os.makedirs(scene_output_dir)

        # 保存掩码矩阵为CSV格式
        np.savetxt(os.path.join(scene_output_dir, f"mask_{scene_index}.csv"), matrix_mask, delimiter=',', fmt='%d')
        export_mitsuba(filepath=os.path.join(scene_output_dir, f"scene_{scene_index}.xml"))

    print(f"✅ 所有 {SCENE_COUNT} 个场景生成完成！每个场景随机生成建筑，并从中抽取8个作为基站（掩码=2）。")
if __name__ == "__main__":
    main()
