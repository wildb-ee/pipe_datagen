import bpy
import random
import math
import os
from mathutils import Vector

# =========================================================================
# CONFIGURATION VARIABLES FOR DATASET
# =========================================================================
# Set this to the folder where you want your dataset saved 

#from dotenv import load_dotenv

#load_dotenv()

#DATASET_DIR = os.getenv("DATASET_DIR")

DATASET_DIR = ""
NUM_SAMPLES = 20      # Number of dataset images to generate
RENDER_RESOLUTION = 640 

TUBE_RADIUS = 1.0
TUBE_DEPTH = 8.0
TUBE_THICKNESS = 0.15

# Small holes for corrosion simulation
HOLE_RADIUS_MIN = 0.05
HOLE_RADIUS_MAX = 0.24          
MASK_PASS_INDEX = 77            

# Create directories if they don't exist
os.makedirs(os.path.join(DATASET_DIR, "ir_images"), exist_ok=True)
os.makedirs(os.path.join(DATASET_DIR, "masks"), exist_ok=True)

# =========================================================================
# 1. COMPOSITOR SETUP (Extract IR and Mask simultaneously)
# =========================================================================
def setup_compositor():
    scene = bpy.context.scene
    tree_name = "Pipeline_Compositor"
    if tree_name in bpy.data.node_groups:
        tree = bpy.data.node_groups[tree_name]
    else:
        tree = bpy.data.node_groups.new(name=tree_name, type='CompositorNodeTree')
        
    scene.compositing_node_group = tree
    tree.nodes.clear()

    rl_node = tree.nodes.new('CompositorNodeRLayers')
    rl_node.location = (-400, 0)
    
    # Use Cryptomatte instead of ID Mask for Eevee compatibility
    crypto_node = tree.nodes.new('CompositorNodeCryptomatteV2')
    crypto_node.location = (0, -150)
    crypto_node.matte_id = "HoleSegmentationMask" # Explicitly track the mask material
    
    out_ir = tree.nodes.new('CompositorNodeOutputFile')
    out_ir.directory = os.path.join(DATASET_DIR, "ir_images")
    out_ir.format.media_type = 'IMAGE'
    out_ir.format.color_mode = 'RGB'
    out_ir.format.file_format = 'PNG'
    if len(out_ir.file_output_items) == 0:
        out_ir.file_output_items.new('RGBA', "ir_####")
    else:
        out_ir.file_output_items[0].path = "ir_####"
    out_ir.location = (300, 150)
    
    out_mask = tree.nodes.new('CompositorNodeOutputFile')
    out_mask.directory = os.path.join(DATASET_DIR, "masks")
    out_mask.format.media_type = 'IMAGE'
    out_mask.format.color_mode = 'BW' 
    out_mask.format.file_format = 'PNG'
    if len(out_mask.file_output_items) == 0:
        out_mask.file_output_items.new('RGBA', "mask_####")
    else:
        out_mask.file_output_items[0].path = "mask_####"
    out_mask.location = (300, -150)
    
    # Wiring the compositor
    tree.links.new(rl_node.outputs['Image'], out_ir.inputs[0])
    tree.links.new(rl_node.outputs['Image'], crypto_node.inputs['Image'])
    tree.links.new(crypto_node.outputs['Matte'], out_mask.inputs[0])

# =========================================================================
# 2. SCENE CLEARING
# =========================================================================
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)

# =========================================================================
# 3. GENERATION LOGIC
# =========================================================================
def generate_pipe():
    # --- Materials ---
    mat = bpy.data.materials.new(name="ProceduralRealisticRust")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    out_node = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    
    # -----------------------------------------------------------
    # 1. THE MAIN MASK (Where is the rust vs. exposed metal?)
    # -----------------------------------------------------------
    noise_mask = nodes.new(type='ShaderNodeTexNoise')
    noise_mask.inputs['Scale'].default_value = random.uniform(1.5, 3.5)
    noise_mask.inputs['Detail'].default_value = 15.0
    noise_mask.inputs['Roughness'].default_value = 0.65

    ramp_mask_sharp = nodes.new(type='ShaderNodeValToRGB')
    ramp_mask_sharp.color_ramp.elements[0].position = 0.35
    ramp_mask_sharp.color_ramp.elements[1].position = 0.65

    # -----------------------------------------------------------
    # 2. COLOR GENERATION 
    # -----------------------------------------------------------
    noise_rust_detail = nodes.new(type='ShaderNodeTexNoise')
    noise_rust_detail.inputs['Scale'].default_value = 12.0
    noise_rust_detail.inputs['Detail'].default_value = 15.0

    ramp_rust_color = nodes.new(type='ShaderNodeValToRGB')
    cr = ramp_rust_color.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.04, 0.02, 0.015, 1.0) # Deep, dark oxidized pitting
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.45, 0.22, 0.05, 1.0)  # Bright orange accent 
    
    el_mid1 = cr.elements.new(0.35)
    el_mid1.color = (0.12, 0.06, 0.04, 1.0)         # Desaturated dark brown
    el_mid2 = cr.elements.new(0.65)
    el_mid2.color = (0.25, 0.11, 0.05, 1.0)         # Dusty medium brown

    mix_base_color = nodes.new(type='ShaderNodeMixRGB')
    mix_base_color.inputs[1].default_value = (0.08, 0.075, 0.07, 1.0) # Dark charcoal base metal
    
    # -----------------------------------------------------------
    # 3. PHYSICAL PROPERTIES (Roughness & Metallic)
    # -----------------------------------------------------------
    ramp_roughness = nodes.new(type='ShaderNodeValToRGB')
    ramp_roughness.color_ramp.elements[0].position = 0.0
    ramp_roughness.color_ramp.elements[0].color = (0.6, 0.6, 0.6, 1.0)  
    ramp_roughness.color_ramp.elements[1].position = 1.0
    ramp_roughness.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1.0) 

    ramp_metallic = nodes.new(type='ShaderNodeValToRGB')
    ramp_metallic.color_ramp.elements[0].position = 0.0
    ramp_metallic.color_ramp.elements[0].color = (0.25, 0.25, 0.25, 1.0) 
    ramp_metallic.color_ramp.elements[1].position = 1.0
    ramp_metallic.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)    

    # -----------------------------------------------------------
    # 4. BUMP MAPPING (Pitting & Flaking)
    # -----------------------------------------------------------
    voronoi_pit = nodes.new(type='ShaderNodeTexVoronoi')
    voronoi_pit.inputs['Scale'].default_value = random.uniform(30.0, 50.0)
    
    mix_bump = nodes.new(type='ShaderNodeMixRGB')
    mix_bump.inputs[1].default_value = (0.5, 0.5, 0.5, 1.0) 
    
    bump = nodes.new(type='ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.65
    bump.inputs['Distance'].default_value = 0.06

    # --- WIRING EVERYTHING TOGETHER ---
    links = mat.node_tree.links
    
    links.new(noise_mask.outputs['Fac'], ramp_mask_sharp.inputs['Fac'])
    links.new(noise_rust_detail.outputs['Fac'], ramp_rust_color.inputs['Fac'])
    links.new(ramp_rust_color.outputs['Color'], mix_base_color.inputs[2])
    links.new(ramp_mask_sharp.outputs['Color'], mix_base_color.inputs['Fac'])
    links.new(mix_base_color.outputs['Color'], bsdf.inputs['Base Color'])
    
    links.new(ramp_mask_sharp.outputs['Color'], ramp_roughness.inputs['Fac'])
    links.new(ramp_roughness.outputs['Color'], bsdf.inputs['Roughness'])
    
    links.new(ramp_mask_sharp.outputs['Color'], ramp_metallic.inputs['Fac'])
    links.new(ramp_metallic.outputs['Color'], bsdf.inputs['Metallic'])
    
    links.new(voronoi_pit.outputs['Distance'], mix_bump.inputs[2])
    links.new(ramp_mask_sharp.outputs['Color'], mix_bump.inputs['Fac'])
    links.new(mix_bump.outputs['Color'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    # --- Segmentation Mask Material ---
    mat_mask = bpy.data.materials.new(name="HoleSegmentationMask")
    mat_mask.use_nodes = True
    mat_mask.pass_index = MASK_PASS_INDEX
    nodes_mask = mat_mask.node_tree.nodes
    nodes_mask.clear()
    node_bsdf = nodes_mask.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.inputs['Base Color'].default_value = (0.01, 0.01, 0.01, 1.0) 
    node_bsdf.inputs['Roughness'].default_value = 1.0
    node_mask_out = nodes_mask.new(type='ShaderNodeOutputMaterial')
    mat_mask.node_tree.links.new(node_bsdf.outputs['BSDF'], node_mask_out.inputs['Surface'])

    # --- Background Void Cylinder ---
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, 
        radius=TUBE_RADIUS + 0.5, 
        depth=TUBE_DEPTH + 1.0, 
        location=(0, 0, 0)
    )
    env_tube = bpy.context.active_object
    env_tube.name = "Void_Environment"
    env_tube.data.materials.append(mat_mask)

    # --- Base Tube ---
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=128, 
        radius=TUBE_RADIUS, 
        depth=TUBE_DEPTH, 
        end_fill_type='NOTHING', 
        location=(0, 0, 0)
    )
    tube = bpy.context.active_object
    tube.name = "Corroded_Rusty_Tube"

    solidify = tube.modifiers.new(name="Thickness", type='SOLIDIFY')
    solidify.thickness = TUBE_THICKNESS
    solidify.offset = 1.0
    bpy.ops.object.shade_smooth()
    tube.data.materials.append(mat)

    # --- Organic Hole Cutters ---
    cutter_collection = bpy.data.collections.new("Organic_Hole_Cutters")
    bpy.context.scene.collection.children.link(cutter_collection)
    
    hole_count = random.randint(30, 60) 
    for i in range(hole_count):
        z = random.uniform(-TUBE_DEPTH/2 + 0.6, TUBE_DEPTH/2 - 0.6)
        angle = random.uniform(0, 2 * math.pi)
        h_radius = random.uniform(HOLE_RADIUS_MIN, HOLE_RADIUS_MAX)
        
        x = TUBE_RADIUS * math.cos(angle)
        y = TUBE_RADIUS * math.sin(angle)
        
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=42, radius=h_radius, depth=1.5, location=(x, y, z)
        )
        cutter = bpy.context.active_object
        
        cutter.data.materials.append(mat_mask)
        
        # Organic Distortion Math
        wave_amp1 = random.uniform(-0.3, 0.3)
        wave_amp2 = random.uniform(-0.15, 0.15)
        freq1 = random.choice([2, 3, 4])
        freq2 = random.choice([5, 7, 9])
        
        for vert in cutter.data.vertices:
            dist_from_center = math.sqrt(vert.co.x**2 + vert.co.y**2)
            if dist_from_center > 0.01:
                vert_angle = math.atan2(vert.co.y, vert.co.x)
                distortion = 1.0 + (wave_amp1 * math.sin(vert_angle * freq1)) + (wave_amp2 * math.cos(vert_angle * freq2))
                vert.co.x *= distortion
                vert.co.y *= distortion
        
        direction = Vector((x, y, 0))
        cutter.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        
        current_coll = cutter.users_collection[0]
        current_coll.objects.unlink(cutter)
        cutter_collection.objects.link(cutter)

    cutter_collection.hide_viewport = True
    cutter_collection.hide_render = True

    # Apply Boolean
    boolean_mod = tube.modifiers.new(name="Cut_Corrosion_Holes", type='BOOLEAN')
    boolean_mod.operation = 'DIFFERENCE'
    boolean_mod.operand_type = 'COLLECTION'
    boolean_mod.collection = cutter_collection
    boolean_mod.solver = 'MANIFOLD'
    
    # PERFORMANCE OPTIMIZATION: Bake the modifier so it doesn't recalculate every frame
    bpy.context.view_layer.objects.active = tube
    bpy.ops.object.modifier_apply(modifier="Cut_Corrosion_Holes")

def update_camera_and_light():
    for name in ["Pipe_Internal_Camera", "InternalLight"]:
        if name in bpy.data.objects:
            obj = bpy.data.objects[name]
            bpy.data.objects.remove(obj, do_unlink=True)
            
    for cam in list(bpy.data.cameras):
        if cam.users == 0:
            bpy.data.cameras.remove(cam)
            
    for light in list(bpy.data.lights):
        if light.users == 0:
            bpy.data.lights.remove(light)

    # --- Camera Generation ---
    camera_data = bpy.data.cameras.new(name="Pipe_Internal_Camera")
    camera_object = bpy.data.objects.new("Pipe_Internal_Camera", camera_data)
    bpy.context.scene.collection.objects.link(camera_object)

    MAX_SAFE_RADIUS = (TUBE_RADIUS - TUBE_THICKNESS) - 0.25  
    cam_angle = random.uniform(0, 2 * math.pi)
    cam_r = random.uniform(0, MAX_SAFE_RADIUS)
    cam_x = cam_r * math.cos(cam_angle)
    cam_y = cam_r * math.sin(cam_angle)
    cam_z = random.uniform(-TUBE_DEPTH/2 + 1.0, TUBE_DEPTH/2 - 1.0) 

    camera_object.location = (cam_x, cam_y, cam_z)

    tar_angle = random.uniform(0, 2 * math.pi)
    tar_r = random.uniform(0, MAX_SAFE_RADIUS)
    tar_x = tar_r * math.cos(tar_angle)
    tar_y = tar_r * math.sin(tar_angle)
    tar_z = random.uniform(-TUBE_DEPTH/2 + 0.5, TUBE_DEPTH/2 - 0.5)

    cam_pos = Vector((cam_x, cam_y, cam_z))
    target_pos = Vector((tar_x, tar_y, tar_z))
    direction = target_pos - cam_pos

    camera_object.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    camera_data.lens = 16
    bpy.context.scene.camera = camera_object
    
    # --- Internal Lighting Generation ---
    light_data = bpy.data.lights.new(name="InternalLight", type='POINT')
    light_data.energy = random.uniform(20, 80)
    light_obj = bpy.data.objects.new(name="InternalLight", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = camera_object.location 

# =========================================================================
# 4. OPTIMIZED EXECUTION LOOP
# =========================================================================

bpy.context.scene.render.resolution_x = RENDER_RESOLUTION
bpy.context.scene.render.resolution_y = RENDER_RESOLUTION
bpy.context.scene.render.engine = 'BLENDER_EEVEE'

bpy.context.scene.cycles.samples = 32        
bpy.context.scene.view_layers["ViewLayer"].use_pass_cryptomatte_material = True

setup_compositor()

for frame in range(1, NUM_SAMPLES + 1):
    print(f"Generating Sample {frame}/{NUM_SAMPLES}...")
    
    if (frame - 1) % 10 == 0:
        clear_scene()
        generate_pipe()
    
    update_camera_and_light()
    bpy.context.scene.frame_set(frame)
    bpy.ops.render.render(write_still=False)

print("Dataset generation complete!")
