import bpy, bmesh, math, time
from mathutils import Vector
t0=time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
# --- fuselage nose: loft of rounded-diamond sections (chined, like a stealth nose)
def section(w,h,chine,n=24):
    pts=[]
    for i in range(n):
        a=2*math.pi*i/n; c,s=math.cos(a),math.sin(a)
        r=1/ (abs(c)**chine+abs(s)**chine)**(1/chine)   # superellipse; chine<2 => diamond-ish
        pts.append((0,w*r*c,h*r*s))
    return pts
bm=bmesh.new(); rings=[]
stations=[(0,0.05,0.04),(1.2,0.55,0.38),(2.6,0.95,0.62),(4.2,1.25,0.78),(6.0,1.4,0.85)]
for x,w,h in stations:
    ring=[bm.verts.new((x,y,z)) for _,y,z in section(w,h,1.35)]; rings.append(ring)
n=len(rings[0])
for a,b in zip(rings,rings[1:]):
    for i in range(n): bm.faces.new((a[i],a[(i+1)%n],b[(i+1)%n],b[i]))
bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
me=bpy.data.meshes.new('nose'); bm.to_mesh(me); nose=bpy.data.objects.new('nose',me); sc.collection.objects.link(nose)
for f in me.polygons: f.use_smooth=True
sub=nose.modifiers.new('sub','SUBSURF'); sub.levels=2; sub.render_levels=2
# --- canopy
bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1,location=(3.4,0,0.7)); cano=bpy.context.object; cano.name='canopy'
cano.scale=(1.6,0.42,0.38); bpy.ops.object.shade_smooth()
# --- vermilion chine line (curve)
cu=bpy.data.curves.new('chine','CURVE'); cu.dimensions='3D'; cu.bevel_depth=0.012
sp=cu.splines.new('POLY'); P=[(0.4,0.3,0),(2.6,0.95,0),(4.2,1.25,0),(6.0,1.4,0)]; sp.points.add(len(P)-1)
for p,c in zip(sp.points,P): p.co=(*c,1)
chine=bpy.data.objects.new('chine.l',cu); sc.collection.objects.link(chine)
# --- materials
def mat(name,rgb,rough=0.6,emit=0):
    m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*rgb,1); b.inputs['Roughness'].default_value=rough
    if emit: b.inputs['Emission Color'].default_value=(*rgb,1); b.inputs['Emission Strength'].default_value=emit
    return m
nose.data.materials.append(mat('graphite',(0.06,0.065,0.07),0.55))
cano.data.materials.append(mat('glass',(0.01,0.015,0.02),0.08))
chine.data.materials.append(mat('vermilion',(0.8,0.12,0.05),0.4,3))
# --- ground, lights, camera
bpy.ops.mesh.primitive_plane_add(size=40,location=(3,0,-0.9)); bpy.context.object.data.materials.append(mat('floor',(0.03,0.035,0.04),0.9))
bpy.ops.object.light_add(type='AREA',location=(6,-4,6)); L=bpy.context.object; L.data.energy=900; L.data.size=6; L.rotation_euler=(0.9,0,0.6)
bpy.ops.object.light_add(type='AREA',location=(-2,5,3)); bpy.context.object.data.energy=150; bpy.context.object.data.size=8
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.016,0.02,0.025,1)
bpy.ops.object.camera_add(location=(-2.5,-5.5,3.2)); cam=bpy.context.object; sc.camera=cam
d=Vector((3.2,0,0.3))-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler(); cam.data.lens=40
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=48; sc.cycles.use_denoising=True
sc.render.resolution_x=960; sc.render.resolution_y=540; sc.render.filepath='/tmp/claude-0/-home-claude/db99bc5e-f420-5311-b102-a9b031c11338/scratchpad/blender/render.png'
bpy.ops.render.render(write_still=True); t1=time.time()
# --- AO bake into vertex colors (applied mesh) for the web
bpy.context.view_layer.objects.active=nose; nose.select_set(True)
bpy.ops.object.modifier_apply(modifier='sub')
nose.data.color_attributes.new('ao','FLOAT_COLOR','POINT'); nose.data.color_attributes.active_color=nose.data.color_attributes['ao']
sc.cycles.samples=32; sc.render.bake.target='VERTEX_COLORS'
for o in bpy.context.selected_objects: o.select_set(False)
nose.select_set(True); bpy.ops.object.bake(type='AO'); t2=time.time()
bpy.ops.export_scene.gltf(filepath='/tmp/claude-0/-home-claude/db99bc5e-f420-5311-b102-a9b031c11338/scratchpad/blender/nose.glb',export_format='GLB',use_selection=False)
print('render %.1fs bake %.1fs total %.1fs verts %d'%(t1-t0,t2-t1,time.time()-t0,len(nose.data.vertices)))
