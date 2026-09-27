# Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
# except for the third-party components listed below.
# Hunyuan 3D does not impose any additional limitations beyond what is outlined
# in the repsective licenses of these third-party components.
# Users must comply with all terms and conditions of original licenses of these third-party
# components and must ensure that the usage of the third party components adheres to
# all relevant laws and regulations.

# For avoidance of doubts, Hunyuan 3D means the large language models and
# their software and algorithms, including trained model weights, parameters (including
# optimizer states), machine-learning model code, inference-enabling code, training-enabling code,
# fine-tuning enabling code and other elements of the foregoing made publicly available
# by Tencent in accordance with TENCENT HUNYUAN COMMUNITY LICENSE AGREEMENT.

import trimesh


def remesh_mesh(mesh_path, remesh_path, method='trimesh', face_count=10000):
    if method == 'trimesh':
        mesh_simplify_trimesh(mesh_path, remesh_path, face_count=face_count)
    else:
        raise f'Method {method} has not been implemented.'


def mesh_simplify_trimesh(inputpath, outputpath, face_count=10000):
    """QEM-decimate mesh. Props target 5k–15k tris before UV."""
    import pymeshlab
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(inputpath, load_in_a_single_layer=True)
    ms.save_current_mesh(outputpath.replace('.glb', '.obj'), save_textures=False)

    current = trimesh.load(outputpath.replace('.glb', '.obj'), force='mesh')
    face_num = current.faces.shape[0]
    # Clamp to prop game-ready band
    target = int(max(5000, min(15000, int(face_count))))

    if face_num > target:
        try:
            current = current.simplify_quadric_decimation(face_count=target)
        except TypeError:
            current = current.simplify_quadric_decimation(target)
    current.export(outputpath)
