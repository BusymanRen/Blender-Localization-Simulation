import bpy
import random
import os
import numpy as np
import sys
from bpy_extras.io_utils import axis_conversion

# Assuming SceneConverter is already in the correct path
sys.path.append(r"./scene_object/mitsuba-blender/io/exporter")
from convert import SceneConverter


# Function to export Mitsuba scene
def export_mitsuba(filepath, use_selection=False, split_files=False, export_ids=True, ignore_background=True,
                   axis_forward='Y', axis_up='Z'):
    print("Starting Mitsuba scene export...")

    # Initialize converter
    converter = SceneConverter(render=False)
    converter.use_selection = use_selection
    converter.ignore_background = ignore_background

    # Set coordinate system conversion matrix
    axis_mat = axis_conversion(to_forward=axis_forward, to_up=axis_up).to_4x4()
    converter.export_ctx.axis_mat = axis_mat
    converter.export_ctx.export_ids = export_ids

    # Set export path and split files options
    converter.set_path(filepath, split_files=split_files)

    # Get Blender current scene dependency graph
    deps_graph = bpy.context.evaluated_depsgraph_get()
    wm = bpy.context.window_manager

    # Display progress bar
    wm.progress_begin(0, len(deps_graph.object_instances))

    # Execute export
    converter.scene_to_dict(deps_graph, wm)
    converter.dict_to_xml()

    wm.progress_end()
    print(f"✅ Export completed: {filepath}")


# Configuration parameters
PLANE_SIZE = 32  # Size of the base plane
CELL_SIZE = 4  # Size of each grid cell
BUILDING_WIDTH = 3  # Random building width
BUILDING_DEPTH = 3  # Random building depth
BUILDING_HEIGHT_NORMAL = 6  # Normal building height
BUILDING_HEIGHT_TALL = 12  # Tall building height
BASE_STATION_WIDTH = 3  # Base station building width
BASE_STATION_DEPTH = 3  # Base station building depth

# Probability control options
SPAWN_PROBABILITY = 0.3  # Probability of spawning a building (0.0-1.0)
SCENE_COUNT = 50  # Total number of unique scenes to generate

# Output directory
OUTPUT_DIR = "./scene_object/output32/"


# Function to create materials
def create_material():
    material_name = "itu_concrete"
    material = bpy.data.materials.get(material_name)
    if material is None:  # Check if material already exists
        material = bpy.data.materials.new(name=material_name)
        material.diffuse_color = (0.8, 0.6, 0.4, 1)  # Set color
    return material


def create_building(i, j, height, material, width, depth):
    x = (i * CELL_SIZE) + CELL_SIZE / 2 - PLANE_SIZE / 2
    y = (j * CELL_SIZE) + CELL_SIZE / 2 - PLANE_SIZE / 2

    # Create building mesh
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, height / 2), scale=(width, depth, height))
    building = bpy.context.active_object
    building.name = f"Building_{i}_{j}"

    # Assign material to the building
    if len(building.data.materials) == 0:
        building.data.materials.append(material)
    else:
        building.data.materials[0] = material

    return building


# Main execution loop
def main():
    # Clear existing objects in the scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Create base plane
    bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Base_Plane"

    # Create material
    material = create_material()
    plane.data.materials.append(material)  # Apply material to base plane

    # Check and create output directory
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Calculate grid dimensions
    grid_count = PLANE_SIZE // CELL_SIZE  # e.g., 8x8 grid

    # Positions for base stations / fixed buildings
    fixed_cells = {
        (0, 0)  # Bottom-left corner
    }

    # Grid cells where building generation is forbidden
    forbidden_cells = set()

    # Set to keep track of unique mask signatures
    generated_masks = set()

    # Generate unique scenes
    scene_index = 0
    max_attempts = SCENE_COUNT * 100  # Safeguard against infinite loops if SCENE_COUNT is too high
    attempts = 0

    while scene_index < SCENE_COUNT and attempts < max_attempts:
        attempts += 1

        # 1. Pre-calculate the matrix mask to check uniqueness before building
        matrix_mask = np.zeros((grid_count, grid_count), dtype=int)

        for i in range(grid_count):
            for j in range(grid_count):
                if (i, j) in forbidden_cells:
                    continue

                # Dynamic index symmetry calculations as per your original layout logic
                symmetric_i = grid_count - 1 - i
                symmetric_j = grid_count - 1 - j

                if (i, j) in fixed_cells:
                    matrix_mask[symmetric_i][symmetric_j] = 2
                elif random.random() <= SPAWN_PROBABILITY:
                    matrix_mask[symmetric_i][symmetric_j] = 1

        # Convert matrix to a tuple structure so it can be hashed and checked in the set
        mask_signature = tuple(map(tuple, matrix_mask))

        if mask_signature in generated_masks:
            continue  # Layout already exists, skip and re-roll

        # Unique layout confirmed! Add it to the tracker
        generated_masks.add(mask_signature)

        # 2. Re-initialize Blender scene for the current valid iteration
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
        plane = bpy.context.active_object
        plane.name = "Base_Plane"
        plane.data.materials.append(material)

        # 3. Build the 3D meshes based on the confirmed unique mask
        for i in range(grid_count):
            for j in range(grid_count):
                symmetric_i = grid_count - 1 - i
                symmetric_j = grid_count - 1 - j

                mask_val = matrix_mask[symmetric_i][symmetric_j]

                if mask_val == 2:
                    height = BUILDING_HEIGHT_TALL
                    create_building(i, j, height, material, BUILDING_WIDTH, BUILDING_DEPTH)
                elif mask_val == 1:
                    height = BUILDING_HEIGHT_NORMAL
                    create_building(i, j, height, material, BUILDING_WIDTH, BUILDING_DEPTH)

        # Create new folder for the current scene
        scene_output_dir = os.path.join(OUTPUT_DIR, f"scene_{scene_index}")
        if not os.path.exists(scene_output_dir):
            os.makedirs(scene_output_dir)

        # Save the mask matrix as a CSV file
        np.savetxt(os.path.join(scene_output_dir, f"mask_{scene_index}.csv"), matrix_mask, delimiter=',', fmt='%d')

        # Export XML file
        export_mitsuba(filepath=os.path.join(scene_output_dir, f"scene_{scene_index}.xml"))

        scene_index += 1

    if scene_index < SCENE_COUNT:
        print(f"Warning: Only generated {scene_index} unique scenes before hitting the safety attempt limit.")
    else:
        print(f"All {SCENE_COUNT} unique scenes generated successfully!")


if __name__ == "__main__":
    main()