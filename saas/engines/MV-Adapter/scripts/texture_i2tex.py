import argparse
import gc
import os
import sys

import torch
from PIL import Image
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

from mvadapter.pipelines.pipeline_texture import ModProcessConfig, TexturePipeline
from mvadapter.utils import make_image_grid
from mvadapter.utils.mesh_utils.mesh_process import process_raw

# Must match inference_ig2mv_* control cameras (pipeline_texture subtracts 90° once).
_AZIMUTH = [0, 90, 180, 270, 180, 180]
_ELEVATION = [0, 0, 0, 0, 89.99, -89.99]
# Match control-render distance in inference_ig2mv_sdxl.py
_CAMERA_DISTANCE = 1.8


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--variant", type=str, default="sdxl", choices=["sdxl", "sd21"])
    # I/O
    parser.add_argument("--mesh", type=str, required=True)
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--text", type=str, default="high quality")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--save_dir", type=str, default="./output")
    parser.add_argument("--save_name", type=str, default="i2tex_sample")
    # Quality
    parser.add_argument("--reference_conditioning_scale", type=float, default=1.0)
    parser.add_argument("--num_inference_steps", type=int, default=40)
    parser.add_argument("--guidance_scale", type=float, default=4.0)
    parser.add_argument("--uv_size", type=int, default=0, help="0 = variant default")
    parser.add_argument("--camera_distance", type=float, default=_CAMERA_DISTANCE)
    # Extra
    parser.add_argument("--preprocess_mesh", action="store_true")
    parser.add_argument("--remove_bg", action="store_true")
    parser.add_argument("--rotation_yaw", type=float, default=0.0, help="Yaw rotation offset in degrees for projection")
    parser.add_argument("--rotation_pitch", type=float, default=0.0, help="Pitch rotation offset in degrees for projection")
    parser.add_argument("--inpaint_mode", type=str, default="uv", choices=["uv", "view"], help="Inpaint blending mode")
    args = parser.parse_args()

    if args.variant == "sdxl":
        from .inference_ig2mv_sdxl import prepare_pipeline, remove_bg, run_pipeline

        base_model = "stabilityai/stable-diffusion-xl-base-1.0"
        vae_model = "madebyollin/sdxl-vae-fp16-fix"
        height = width = 768
        uv_size = args.uv_size or 2048  # 2048 is enough for ~2k–25k game meshes
    elif args.variant == "sd21":
        from .inference_ig2mv_sd import prepare_pipeline, remove_bg, run_pipeline

        base_model = "stabilityai/stable-diffusion-2-1-base"
        vae_model = None
        height = width = 512
        uv_size = args.uv_size or 2048
    else:
        raise ValueError(f"Invalid variant: {args.variant}")

    device = args.device
    num_views = 6

    # Unwrap (and optional cleanup) BEFORE multiview so control maps and bake share geometry.
    file_suffix = os.path.splitext(args.mesh)[-1]
    mesh_unwarp = args.mesh.replace(file_suffix, f"_unwarp{file_suffix}")
    print(f"[texture] UV unwrap → {mesh_unwarp} (preprocess={args.preprocess_mesh})")
    process_raw(
        args.mesh,
        mesh_unwarp,
        preprocess=args.preprocess_mesh,
        device="cpu",
        uv_size=uv_size,
    )
    mesh_path = mesh_unwarp

    # Prepare pipelines
    pipe = prepare_pipeline(
        base_model=base_model,
        vae_model=vae_model,
        unet_model=None,
        lora_model=None,
        adapter_path="huanngzh/mv-adapter",
        scheduler=None,
        num_views=num_views,
        device=device,
        dtype=torch.float16,
    )
    if args.remove_bg:
        birefnet = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet", trust_remote_code=True
        )
        birefnet.to(args.device).eval()
        transform_image = transforms.Compose(
            [
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        raw_img = Image.open(args.image) if isinstance(args.image, str) else args.image
        clean_img = remove_bg(raw_img, birefnet, transform_image, args.device)
        del birefnet
        torch.cuda.empty_cache()
        gc.collect()
        image_input = clean_img
        remove_bg_fn = None
    else:
        image_input = args.image
        remove_bg_fn = None

    os.makedirs(args.save_dir, exist_ok=True)

    # 1. Geometry-conditioned multiview on the *same* mesh used for bake
    images, _, _, _ = run_pipeline(
        pipe,
        mesh_path=mesh_path,
        num_views=num_views,
        text=args.text,
        image=image_input,
        height=height,
        width=width,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
        reference_conditioning_scale=args.reference_conditioning_scale,
        negative_prompt=(
            "watermark, logo, text, ugly, deformed, noisy, blurry, low contrast, "
            "extra limbs, missing limbs, cropped"
        ),
        device=device,
        remove_bg_fn=remove_bg_fn,
    )
    mv_path = os.path.join(args.save_dir, f"{args.save_name}.png")
    make_image_grid(images, rows=1).save(mv_path)

    # Free diffusion weights before UV bake (avoids CUDA OOM on ~20GB cards)
    del images, pipe
    gc.collect()
    torch.cuda.empty_cache()

    # 2. Initialize TexturePipeline only when needed after diffusion is completely freed
    texture_pipe = TexturePipeline(
        upscaler_ckpt_path="./checkpoints/RealESRGAN_x2plus.pth",
        inpaint_ckpt_path="./checkpoints/big-lama.pt",
        device=device,
    )
    print("Texture pipeline ready.")

    # 3. Project multiviews → UV (already unwrapped; do not shift azimuth again)
    out = texture_pipe(
        mesh_path=mesh_path,
        save_dir=args.save_dir,
        save_name=args.save_name,
        uv_unwarp=False,
        preprocess_mesh=False,
        uv_size=uv_size,
        rgb_path=mv_path,
        rgb_process_config=ModProcessConfig(
            view_upscale=True,
            inpaint_mode=args.inpaint_mode,
            view_inpaint_min_rounds=1,
            view_inpaint_max_rounds=2,
        ),
        camera_azimuth_deg=[float((az + args.rotation_yaw) % 360) for az in _AZIMUTH],
        camera_elevation_deg=[float(el + args.rotation_pitch) for el in _ELEVATION],
        camera_distance=args.camera_distance,
        camera_ortho_scale=1.1,
        # Prefer crisp projection over soft poisson melt
        uv_inpaint_use_network=True,
        poisson_reprojection=False,
    )
    print(f"Output saved to {out.shaded_model_save_path}")
