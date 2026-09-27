import numpy as np
import open3d as o3d
import pymeshlab
import trimesh
try:
    from pymeshlab import Percentage
except ImportError:  # pymeshlab >= 2023.12
    from pymeshlab import PercentageValue as Percentage


### Mesh Utils ###
##### read mesh
def read_mesh_from_path(mesh_path):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(mesh_path)
    return ms


def mesh_to_meshlab(vertices, faces):
    mesh = pymeshlab.Mesh(vertex_matrix=vertices, face_matrix=faces)
    ms = pymeshlab.MeshSet()
    ms.add_mesh(mesh)
    return ms


def meshlab_to_mesh(ms):
    m = ms.current_mesh()
    return m.vertex_matrix(), m.face_matrix(), m.vertex_normal_matrix()


##### decimation
def decimate_quadric_edge_collapse_with_texture(
    ms, targetfacenum=None, preservenormal=True, verbose=False
):
    # targetfacenum: int, Target number of faces.
    # preservenormal: bool, Preserve the normals of the original mesh.
    if verbose:
        print("Starting decimation ...  ")
    m = ms.current_mesh()
    if targetfacenum is None:
        targetfacenum = int(m.face_number() * 0.5)
    if verbose:
        print("... Initial face number is %d ... " % m.face_number())
    ms.meshing_decimation_quadric_edge_collapse_with_texture(
        targetfacenum=targetfacenum, preservenormal=preservenormal
    )
    if verbose:
        print("... Decimated face number is %d ... " % m.face_number())
        print("Decimation done!\n ")


def decimate_quadric_edge_collapse(
    ms, targetfacenum=None, preservenormal=True, verbose=False
):
    # targetfacenum: int, Target number of faces.
    # preservenormal: bool, Preserve the normals of the original mesh.
    if verbose:
        print("Starting decimation ...  ")
    m = ms.current_mesh()
    if targetfacenum is None:
        targetfacenum = int(m.face_number() * 0.5)
    if verbose:
        print("... Initial face number is %d ... " % m.face_number())
    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=targetfacenum, preservenormal=preservenormal
    )
    if verbose:
        print("... Decimated face number is %d ... " % m.face_number())
        print("Decimation done!\n ")


##### vertex merge
def merge_close_vertices(ms, threshold=0.0001, verbose=False):
    # threshold: float, Merge together all the vertices that are nearer than the specified threshold.
    if verbose:
        print("Starting merge vertices ...  ")
    m = ms.current_mesh()
    if verbose:
        print("... Initial vertex number is %d ... " % m.vertex_number())
    ms.meshing_merge_close_vertices(threshold=Percentage(threshold * 100))
    if verbose:
        print("... Merged vertex number is %d ... " % m.vertex_number())
        print("Merge vertices done!\n ")


##### Island Removal
def remove_isolated_pieces(ms, mincomponentsize=25, diameter=None, verbose=False):
    # mincomponentsize: Delete isolated connected components composed by a limited number of triangles
    # diameter: Delete isolated connected components whose diameter is smaller than the specified constant
    if verbose:
        print("Starting remove isolated pieces ...  ")
    m = ms.current_mesh()
    if verbose:
        print("... Initial face number is %d ... " % m.face_number())
    if diameter is None:
        ms.meshing_remove_connected_component_by_face_number(
            mincomponentsize=mincomponentsize, removeunref=True
        )
    else:
        ms.meshing_remove_connected_component_by_diameter(
            mincomponentdiag=Percentage(diameter), removeunref=True
        )
    if verbose:
        print("... Isolated removed face number is %d ... " % m.face_number())
        print("Remove isolated pieces done!\n ")


##### hole filling
def fix_hole(ms, maxholesize=30, verbose=False):
    # maxholesize: int, Maximum size of the hole to be filled.
    if verbose:
        print("Starting fix holes ...  ")
    m = ms.current_mesh()
    if verbose:
        print("... Initial face number is %d ... " % m.face_number())
    ms.meshing_close_holes(maxholesize=maxholesize)
    if verbose:
        print("... Fixed hole face number is %d ... " % m.face_number())
        print("Fix holes done!\n ")


##### repair non manifold edges
def repair_non_manifold(ms, verbose=False):
    if verbose:
        print("Starting repair non manifold edges ...  ")
    m = ms.current_mesh()
    if verbose:
        print("... Initial face number is %d ... " % m.face_number())
    ms.meshing_repair_non_manifold_edges()
    ms.meshing_repair_non_manifold_vertices(vertdispratio=0.1)
    ms.meshing_remove_duplicate_faces()
    if verbose:
        print("... Fixed non manifold edges face number is %d ... " % m.face_number())
        print("Repair non manifold edges done!\n ")


##### laplacian_smooth
def laplacian_smooth(ms, stepsmoothnum=3, verbose=False):
    # stepsmoothnum: int, Number of smoothing steps to be performed
    if verbose:
        print("Starting laplacian smooth ...  ")
    m = ms.current_mesh()
    ms.apply_coord_laplacian_smoothing(stepsmoothnum=stepsmoothnum)
    if verbose:
        print("Laplacian smooth done!\n ")


##### taubin_smooth
def taubin_smooth(ms, stepsmoothnum=3, verbose=False):
    if verbose:
        print("Starting Taubin smooth ...  ")
    m = ms.current_mesh()
    ms.apply_coord_taubin_smoothing(stepsmoothnum=stepsmoothnum)
    if verbose:
        print("Taubin smooth done!\n ")


##### compute_normal
def compute_normal(ms, weightmode="Simple Average", verbose=False):
    if verbose:
        print("Starting compute_normal_per_vertex ...  ")
    m = ms.current_mesh()
    ms.compute_normal_per_vertex(weightmode=weightmode)
    if verbose:
        print("compute_normal_per_vertex done!\n ")


### Pre-process Mesh ###
def process_mesh(
    vertices,
    faces,
    threshold=0.0001,
    mincomponentRatio=0.02,
    targetfacenum=50000,
    maxholesize=30,
    stepsmoothnum=10,
    verbose=False,
):
    ms = mesh_to_meshlab(vertices, faces)

    ### Vertex Merge
    merge_close_vertices(ms, threshold=threshold, verbose=verbose)

    ### Island Removal
    faces = ms.current_mesh().face_matrix()
    remove_isolated_pieces(
        ms, mincomponentsize=int(len(faces) * mincomponentRatio), verbose=verbose
    )

    ### Hole Filling
    repair_non_manifold(ms)  # repair before fix hole
    fix_hole(ms, maxholesize=maxholesize, verbose=verbose)

    ### Taubin Smoothing
    taubin_smooth(ms, stepsmoothnum=stepsmoothnum, verbose=verbose)

    vertices, faces, _ = meshlab_to_mesh(ms)
    if faces.shape[0] > targetfacenum:
        device = o3d.core.Device("CPU:0")
        dtype_f = o3d.core.float32
        dtype_i = o3d.core.int64
        mesh = o3d.t.geometry.TriangleMesh(device)
        mesh.vertex.positions = o3d.core.Tensor(
            vertices.astype(np.float32), dtype_f, device
        )
        mesh.triangle.indices = o3d.core.Tensor(faces.astype(np.int64), dtype_i, device)
        simplified_mesh = mesh.simplify_quadric_decimation(
            target_reduction=1.0 - float(targetfacenum) / faces.shape[0]
        )
        ms.clear()
        vertices = simplified_mesh.vertex.positions.numpy()
        faces = simplified_mesh.triangle.indices.numpy()
        mesh = pymeshlab.Mesh(vertex_matrix=vertices, face_matrix=faces)
        ms.add_mesh(mesh)

    ### Mesh Simplification/Decimation
    # decimate_quadric_edge_collapse(ms, targetfacenum=targetfacenum, verbose=verbose)
    taubin_smooth(ms, stepsmoothnum=stepsmoothnum, verbose=verbose)
    repair_non_manifold(ms, verbose=verbose)
    compute_normal(ms, verbose=verbose)
    return meshlab_to_mesh(ms)


### UV Un-Warp ###
# Reworked from scratch: use Hunyuan3D-Paint's xatlas remap (mesh_uv_wrap) instead of
# Open3D UVAtlas + UV-hash welding. UVAtlas is brittle on TripoSG (non-manifold /
# 0x80004005) and the old weld path produced scrambled bakes (job 13/14).


def _clean_mesh_for_uv(vertices, faces):
    """Light cleanup before xatlas (no UVAtlas manifold requirements)."""
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    if len(mesh.faces) > 0:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            components.sort(key=lambda m: len(m.faces), reverse=True)
            keep = [components[0]]
            main_faces = max(len(components[0].faces), 1)
            for c in components[1:]:
                if len(c.faces) >= max(50, int(0.01 * main_faces)):
                    keep.append(c)
            mesh = trimesh.util.concatenate(keep) if len(keep) > 1 else keep[0]
            mesh.merge_vertices()
            mesh.remove_unreferenced_vertices()
    return (
        np.asarray(mesh.vertices, dtype=np.float32),
        np.asarray(mesh.faces, dtype=np.int64),
    )


def mesh_uv_wrap(vertices, faces, *, resolution=2048, padding=2):
    """Hunyuan3D-style xatlas unwrap with seam-aware vertex remap.

    Returns ``(vertices, faces, uvs_per_vertex)`` — same contract as
    ``hy3dgen.texgen.utils.uv_warp_utils.mesh_uv_wrap``.
    """
    import xatlas

    v = np.asarray(vertices, dtype=np.float32)
    f = np.asarray(faces, dtype=np.uint32)

    # Prefer Atlas API when pack options are supported; else plain parametrize
    # (installed xatlas bindings often reject chart_options kwargs — see job_14).
    vmapping = indices = uvs = None
    try:
        atlas = xatlas.Atlas()
        atlas.add_mesh(v, f)
        pack_opts = xatlas.PackOptions()
        pack_opts.resolution = int(resolution)
        pack_opts.padding = int(padding)
        try:
            atlas.generate(xatlas.ChartOptions(), pack_opts)
        except TypeError:
            atlas.generate()
        vmapping, indices, uvs = atlas.get_mesh(0)
    except Exception as exc:
        print(f"[uv] Atlas.generate soft-fail ({exc}); parametrize()", flush=True)
        vmapping, indices, uvs = xatlas.parametrize(v, f)

    new_vertices = v[np.asarray(vmapping, dtype=np.int64)]
    new_faces = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    uvs = np.asarray(uvs, dtype=np.float32)
    print(
        f"[uv] xatlas wrap: V {len(v)}→{len(new_vertices)} "
        f"F {len(f)}→{len(new_faces)} res={resolution}",
        flush=True,
    )
    return new_vertices, new_faces, uvs


# Back-compat aliases used by older callers / tests
def uv_parameterize_xatlas(vertices, faces, *, resolution=2048, padding=2):
    v, f, uvs = mesh_uv_wrap(vertices, faces, resolution=resolution, padding=padding)
    return v, f, uvs[f].reshape(-1, 3, 2).astype(np.float32)


def uv_unwrap(vertices, faces, *, size=2048):
    """Clean → xatlas remap. Returns ``(vertices, faces, uvs_per_vertex)``."""
    v, f = _clean_mesh_for_uv(vertices, faces)
    print(f"[uv] cleaned mesh V={len(v)} F={len(f)}", flush=True)
    return mesh_uv_wrap(v, f, resolution=int(size) or 2048, padding=2)


### Pack All ###
def process_raw(mesh_path, save_path, preprocess=True, device="cpu", uv_size=2048):
    """Preprocess (optional) + xatlas UV wrap → export GLB with vertex UVs.

    Matches Hunyuan3D-Paint's unwrap model: remapped topology + per-vertex UVs.
    Skips Open3D UVAtlas and the old UV-hash corner weld (scramble source).
    """
    del device  # export is CPU; kept for API compatibility
    scene = trimesh.load(mesh_path, force="mesh", process=False)
    if isinstance(scene, trimesh.Trimesh):
        mesh = scene
    elif isinstance(scene, trimesh.scene.Scene):
        mesh = trimesh.Trimesh()
        for obj in scene.geometry.values():
            mesh = trimesh.util.concatenate([mesh, obj])
    else:
        raise ValueError(f"Unknown mesh type at {mesh_path}.")

    vertices = mesh.vertices
    faces = mesh.faces

    mesh_post_process_options = {
        "mincomponentRatio": 0.02,
        "targetfacenum": 50000,
        "maxholesize": 100,
        "stepsmoothnum": 10,
        "verbose": False,
    }

    if preprocess:
        v_pos, t_pos_idx, _normals = process_mesh(
            vertices=vertices,
            faces=faces,
            **mesh_post_process_options,
        )
    else:
        v_pos, t_pos_idx = vertices, faces

    v_pos, t_pos_idx, v_tex = uv_unwrap(
        v_pos, t_pos_idx, size=int(uv_size) or 2048
    )
    # glTF / trimesh convention: flip V (same as upstream MV-Adapter)
    uv_to_save = np.asarray(v_tex, dtype=np.float32).copy()
    uv_to_save[:, 1] = 1.0 - uv_to_save[:, 1]

    tmesh = trimesh.Trimesh(
        vertices=np.asarray(v_pos, dtype=np.float32),
        faces=np.asarray(t_pos_idx, dtype=np.int64),
        process=False,
    )
    tmesh.visual = trimesh.visual.TextureVisuals(uv=uv_to_save)
    tmesh.export(save_path)
    print(
        f"[uv] wrote {save_path} V={len(tmesh.vertices)} F={len(tmesh.faces)}",
        flush=True,
    )
