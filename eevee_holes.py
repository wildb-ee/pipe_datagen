import bpy
import random
import math
import os
from mathutils import Vector

# =========================================================================
# CONFIGURATION VARIABLES FOR DATASET
# =========================================================================
DATASET_DIR = "" 
NUM_SAMPLES = 200    
RENDER_RESOLUTION = 512 

TUBE_RADIUS = 1.0
TUBE_DEPTH = 8.0
TUBE_THICKNESS = 0.15

# Small holes for corrosion simulation
HOLE_RADIUS_MIN = 0.05
HOLE_RADIUS_MAX = 0.24          
MASK_PASS_INDEX = 77            

# Create directories if they don't exist
if DATASET_DIR:
    os.makedirs(os.path.join(DATASET_DIR, "images"), exist_ok=True)
    os.makedirs(os.path.join(DATASET_DIR, "masks"), exist_ok=True)

# =========================================================================
# 1. COMPOSITOR SETUP
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
    
    crypto_node = tree.nodes.new('CompositorNodeCryptomatteV2')
    crypto_node.location = (0, -150)
    crypto_node.matte_id = "HoleSegmentationMask" 
    
    # --- RGB IMAGE OUTPUT ---
    out_ir = tree.nodes.new('CompositorNodeOutputFile')
    if DATASET_DIR:
        out_ir.directory = os.path.join(DATASET_DIR, "images")
    out_ir.format.media_type = 'IMAGE'
    out_ir.format.color_mode = 'RGB' 
    out_ir.format.file_format = 'PNG'
    if len(out_ir.file_output_items) == 0:
        out_ir.file_output_items.new('RGBA', "image_####")
    else:
        out_ir.file_output_items[0].path = "image_####"
    out_ir.location = (300, 150)
    
    # --- MASK OUTPUT ---
    out_mask = tree.nodes.new('CompositorNodeOutputFile')
    if DATASET_DIR:
        out_mask.directory = os.path.join(DATASET_DIR, "masks")
    out_mask.format.media_type = 'IMAGE'
    out_mask.format.color_mode = 'BW'
    out_mask.format.color_depth = '8' 
    out_mask.format.file_format = 'PNG'
    
    out_mask.format.color_management = 'OVERRIDE'
    out_mask.format.view_settings.view_transform = 'Standard'
    out_mask.format.view_settings.look = 'None'
    
    if len(out_mask.file_output_items) == 0:
        out_mask.file_output_items.new('RGBA', "mask_####")
    else:
        out_mask.file_output_items[0].path = "mask_####"
    out_mask.location = (300, -150)
    
    # --- WIRING ---
    tree.links.new(rl_node.outputs['Image'], out_ir.inputs[0])
    tree.links.new(rl_node.outputs['Image'], crypto_node.inputs['Image'])
    
    # Convert Cryptomatte output into a strict binary mask
    math_node = tree.nodes.new('ShaderNodeMath')
    math_node.operation = 'GREATER_THAN'
    math_node.inputs[1].default_value = 0.5
    math_node.location = (150, -150)
    
    tree.links.new(crypto_node.outputs['Matte'], math_node.inputs[0])
    tree.links.new(math_node.outputs['Value'], out_mask.inputs[0])
    
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
    # --- MASTER RANDOMIZATION PARAMETERS ---
    corrosion_degree = random.uniform(0.0, 1.0) 
    
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
    # Vary the size of the rust patches
    noise_mask.inputs['Scale'].default_value = random.uniform(0.5, 8.0) 
    noise_mask.inputs['Detail'].default_value = 15.0
    noise_mask.inputs['Roughness'].default_value = random.uniform(0.5, 0.8)

    ramp_mask_sharp = nodes.new(type='ShaderNodeValToRGB')
    
    # Map corrosion_degree to the color ramp thresholds
    if corrosion_degree < 0.05:
        # Guarantee perfectly clean
        p1, p2 = 1.1, 1.2 
    elif corrosion_degree > 0.95:
        # Guarantee entirely covered in rust
        p1, p2 = -0.1, 0.0 
    else:
        # Interpolate threshold based on degree
        threshold = 1.0 - ((corrosion_degree - 0.05) / 0.9)
        p1 = threshold - random.uniform(0.05, 0.15)
        p2 = threshold + random.uniform(0.05, 0.15)
        
    ramp_mask_sharp.color_ramp.elements[0].position = p1
    ramp_mask_sharp.color_ramp.elements[1].position = p2

    # -----------------------------------------------------------
    # 2. COLOR GENERATION (Varying Rust Colors)
    # -----------------------------------------------------------
    noise_rust_detail = nodes.new(type='ShaderNodeTexNoise')
    # Vary the graininess of the rust color
    noise_rust_detail.inputs['Scale'].default_value = random.uniform(5.0, 25.0) 
    noise_rust_detail.inputs['Detail'].default_value = 15.0

    ramp_rust_color = nodes.new(type='ShaderNodeValToRGB')
    cr = ramp_rust_color.color_ramp
    
    # Randomize rust hues (Deep darks, vibrant oranges, flat browns)
    color_dark_pit = (random.uniform(0.0, 0.05), random.uniform(0.0, 0.03), random.uniform(0.0, 0.02), 1.0)
    color_bright = (random.uniform(0.3, 0.6), random.uniform(0.1, 0.25), random.uniform(0.02, 0.08), 1.0)
    color_mid1 = (random.uniform(0.08, 0.15), random.uniform(0.04, 0.08), random.uniform(0.02, 0.05), 1.0)
    color_mid2 = (random.uniform(0.15, 0.3), random.uniform(0.08, 0.15), random.uniform(0.03, 0.08), 1.0)

    cr.elements[0].position = 0.0
    cr.elements[0].color = color_dark_pit
    cr.elements[1].position = 1.0
    cr.elements[1].color = color_bright
    
    el_mid1 = cr.elements.new(0.35)
    el_mid1.color = color_mid1
    el_mid2 = cr.elements.new(0.65)
    el_mid2.color = color_mid2

    mix_base_color = nodes.new(type='ShaderNodeMixRGB')
    # Randomize base metal color (dark iron to bright steel)
    base_gray = random.uniform(0.05, 0.3)
    mix_base_color.inputs[1].default_value = (base_gray, base_gray, base_gray, 1.0)
    
    # -----------------------------------------------------------
    # 3. PHYSICAL PROPERTIES (Roughness & Metallic)
    # -----------------------------------------------------------
    ramp_roughness = nodes.new(type='ShaderNodeValToRGB')
    ramp_roughness.color_ramp.elements[0].position = 0.0
    # Clean metal roughness varies
    metal_roughness = random.uniform(0.2, 0.6)
    ramp_roughness.color_ramp.elements[0].color = (metal_roughness, metal_roughness, metal_roughness, 1.0)  
    ramp_roughness.color_ramp.elements[1].position = 1.0
    # Rust is always highly rough
    ramp_roughness.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1.0) 

    ramp_metallic = nodes.new(type='ShaderNodeValToRGB')
    ramp_metallic.color_ramp.elements[0].position = 0.0
    # Clean metal is highly metallic
    metal_factor = random.uniform(0.6, 1.0)
    ramp_metallic.color_ramp.elements[0].color = (metal_factor, metal_factor, metal_factor, 1.0) 
    ramp_metallic.color_ramp.elements[1].position = 1.0
    # Rust is non-metallic
    ramp_metallic.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)    

    # -----------------------------------------------------------
    # 4. BUMP MAPPING (Pitting & Flaking)
    # -----------------------------------------------------------
    voronoi_pit = nodes.new(type='ShaderNodeTexVoronoi')
    # Vary the frequency of the pits
    voronoi_pit.inputs['Scale'].default_value = random.uniform(15.0, 80.0)
    
    mix_bump = nodes.new(type='ShaderNodeMixRGB')
    mix_bump.inputs[1].default_value = (0.5, 0.5, 0.5, 1.0) 
    
    bump = nodes.new(type='ShaderNodeBump')
    # Randomize how aggressive the bump mapping is
    bump.inputs['Strength'].default_value = random.uniform(0.3, 0.9)
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

    # --- Organic Hole Cutters (Based on Corrosion Degree) ---
    cutter_collection = bpy.data.collections.new("Organic_Hole_Cutters")
    bpy.context.scene.collection.children.link(cutter_collection)
    
    # If the pipe is relatively clean, don't generate any holes
    if corrosion_degree < 0.2:
        hole_count = 0
    else:
        # Scale the number of holes by how severe the corrosion is
        max_holes = int(80 * corrosion_degree)
        hole_count = random.randint(int(max_holes * 0.4), max_holes) 
        
    for i in range(hole_count):
        z = random.uniform(-TUBE_DEPTH/2 + 0.6, TUBE_DEPTH/2 - 0.6)
        angle = random.uniform(0, 2 * math.pi)
        
        # Severe corrosion allows for larger holes
        h_rad_max_adjusted = HOLE_RADIUS_MAX * (0.5 + (corrosion_degree * 0.5))
        h_radius = random.uniform(HOLE_RADIUS_MIN, h_rad_max_adjusted)
        
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

    # Apply Boolean only if there are holes
    if hole_count > 0:
        boolean_mod = tube.modifiers.new(name="Cut_Corrosion_Holes", type='BOOLEAN')
        boolean_mod.operation = 'DIFFERENCE'
        boolean_mod.operand_type = 'COLLECTION'
        boolean_mod.collection = cutter_collection
        boolean_mod.solver = 'MANIFOLD'
        
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

    # Position the camera inside the tube
    MAX_SAFE_RADIUS = (TUBE_RADIUS - TUBE_THICKNESS) - 0.25  
    cam_angle = random.uniform(0, 2 * math.pi)
    cam_r = random.uniform(0, MAX_SAFE_RADIUS)
    cam_x = cam_r * math.cos(cam_angle)
    cam_y = cam_r * math.sin(cam_angle)
    cam_z = random.uniform(-TUBE_DEPTH/2 + 1.0, TUBE_DEPTH/2 - 1.0) 

    camera_object.location = (cam_x, cam_y, cam_z)

    # --- NEW WALL-FACING DIRECTION LOGIC ---
    # 1. Choose a random horizontal angle (0 to 360 degrees) to face a side wall
    look_angle = random.uniform(0, 2 * math.pi)
    
    # 2. Add a very slight vertical tilt (pitch) so it's not perfectly generic,
    # but keep it low enough that it never looks down to the end holes
    look_tilt = random.uniform(-0.15, 0.15) 

    # 3. Formulate the direction vector pointing outward toward the cylinder wall
    direction = Vector((
        math.cos(look_angle),
        math.sin(look_angle),
        look_tilt
    ))

    # Apply the rotation pointing directly at the wall vector
    camera_object.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    
    # Slightly widen the lens field of view to capture more wall surface up close
    camera_data.lens = 14 
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

bpy.context.scene.render.dither_intensity = 0.0

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
    if DATASET_DIR:
        bpy.ops.render.render(write_still=True)

print("Dataset generation complete!")