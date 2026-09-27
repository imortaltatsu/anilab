#!/usr/bin/env python3
"""Local T-pose reference image via FLUX.2 [klein] (BF16 Diffusers pipeline).

BFL's official FP8 single-file is incompatible with current diffusers
``from_single_file`` (``weight_scale`` keys match ``\".weight\" in key`` and
crash on ``torch.chunk``). We either:

1. Load the full BF16 pipeline from a local / Hub snapshot, or
2. Materialize FP8 → BF16 safetensors (dequant + drop scale keys) then inject.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path


def build_tpose_prompt(user_prompt: str) -> tuple[str, str]:
    subject = " ".join(user_prompt.strip().split())
    for junk in (
        "standing pose",
        "standing",
        "full body",
        "t-pose",
        "t pose",
        "a-pose",
        "a pose",
        "facing camera",
        "character sheet",
        "turnaround",
        "reference sheet",
    ):
        low = subject.lower()
        if junk in low:
            i = low.find(junk)
            subject = (subject[:i] + subject[i + len(junk) :]).strip(" ,")
            subject = " ".join(subject.split())
    if not subject:
        subject = "character"

    prompt = (
        f"{subject}. "
        "Single character only, one figure, no collage. "
        "Strict T-pose: both arms fully extended horizontally to the sides forming a T, "
        "palms facing the camera, legs straight, feet flat facing forward. "
        "Front orthographic view, body square to camera, head looking forward. "
        "Full body visible head to toe with empty margin, perfectly centered. "
        "Plain seamless light grey studio background, soft even lighting, sharp detail, "
        "no text, no watermark, no logo."
    )
    negative = (
        "multiple figures, collage, character sheet, turnaround, grid, "
        "dynamic pose, beauty pose, arms down, arms bent, A-pose, cropped, "
        "missing limbs, extra limbs, text, watermark, blurry, melted"
    )
    return prompt, negative


def _is_flux2_klein(model: str) -> bool:
    m = model.lower()
    if "flux.2-klein" in m or "flux2-klein" in m or "flux-2-klein" in m:
        return True
    idx = Path(model) / "model_index.json"
    if idx.is_file():
        try:
            import json

            return "Flux2Klein" in json.loads(idx.read_text()).get("_class_name", "")
        except Exception:
            return False
    return False


def _resolve_fp8_file(fp8_transformer: str) -> Path:
    from huggingface_hub import hf_hub_download

    p = Path(fp8_transformer)
    if p.is_dir():
        cands = list(p.glob("*-fp8.safetensors")) + list(p.glob("*fp8*.safetensors"))
        if not cands:
            raise FileNotFoundError(f"no fp8 safetensors in {p}")
        return cands[0]
    if p.is_file():
        return p
    fname = (
        "flux-2-klein-9b-fp8.safetensors"
        if "9b" in fp8_transformer.lower()
        else "flux-2-klein-4b-fp8.safetensors"
    )
    return Path(hf_hub_download(fp8_transformer, filename=fname))


def _materialize_bfl_fp8_to_bf16(fp8_path: Path, out_path: Path) -> Path:
    """Dequantize BFL float8 weights and drop scale keys so Diffusers conversion works."""
    import torch
    from safetensors.torch import load_file, save_file

    print(f"[t2i] dequantizing FP8 → BF16: {fp8_path}", flush=True)
    raw = load_file(str(fp8_path), device="cpu")
    out: dict = {}
    skipped = 0
    for key, tensor in raw.items():
        # Diffusers matches ``\".weight\" in key``, which incorrectly hits ``weight_scale``.
        if key.endswith(".weight_scale") or key.endswith(".input_scale"):
            skipped += 1
            continue
        if key.endswith(".weight") and tensor.dtype == getattr(torch, "float8_e4m3fn", type(None)):
            scale_key = f"{key}_scale"
            scale = raw.get(scale_key)
            if scale is None:
                # Some dumps use ``.weight_scale`` adjacent naming already handled above.
                scale = raw.get(key.replace(".weight", ".weight_scale"))
            if scale is None:
                raise KeyError(f"missing scale for FP8 weight {key}")
            tensor = (tensor.to(torch.float32) * scale.to(torch.float32)).to(torch.bfloat16)
        elif key.endswith(".scale"):
            # RMSNorm scales stay as-is (BF16 already in BFL dump).
            tensor = tensor.to(torch.bfloat16) if tensor.is_floating_point() else tensor
        elif tensor.is_floating_point() and tensor.dtype != torch.bfloat16:
            # Keep biases / misc floats in bf16 for the converter.
            if tensor.dtype not in (torch.float32, torch.bfloat16, torch.float16):
                tensor = tensor.to(torch.float32)
            if key.endswith((".weight", ".bias")) or tensor.ndim >= 1:
                tensor = tensor.to(torch.bfloat16)
        out[key] = tensor

    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(out, str(out_path))
    print(
        f"[t2i] wrote dequantized transformer ({len(out)} tensors, skipped {skipped} scales) → {out_path}",
        flush=True,
    )
    return out_path


def _transformer_ready(pipe_id: str) -> bool:
    p = Path(pipe_id)
    if not p.is_dir():
        return True  # Hub id — from_pretrained will fetch
    tdir = p / "transformer"
    if not tdir.is_dir():
        return False
    # Need actual weight shards, not just config.json
    return any(tdir.glob("*.safetensors")) or any(tdir.glob("*.bin"))


def _load_flux2_klein(
    *,
    model: str,
    base_model: str,
    fp8_transformer: str | None,
    dtype,
    device: str,
    offload: bool,
):
    """Load Flux2KleinPipeline. Prefer BF16 snapshot; optionally inject dequantized FP8."""
    from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel

    pipe_id = model
    transformer = None

    # Prefer full BF16 pipeline when local transformer weights exist.
    use_fp8 = bool(fp8_transformer and str(fp8_transformer).strip())
    if use_fp8 and not _transformer_ready(pipe_id) and not _transformer_ready(base_model):
        print("[t2i] BF16 transformer missing — using dequantized FP8 path", flush=True)
    elif use_fp8 and _transformer_ready(pipe_id):
        # BF16 available: skip broken raw FP8 injection unless forced via YEETGEN_T2I_FORCE_FP8=1
        import os

        if os.environ.get("YEETGEN_T2I_FORCE_FP8", "").strip() not in ("1", "true", "True"):
            print("[t2i] BF16 transformer present — skipping FP8", flush=True)
            use_fp8 = False

    if use_fp8:
        fp8_path = _resolve_fp8_file(fp8_transformer)  # type: ignore[arg-type]
        cache_dir = Path(fp8_path).parent / ".dequant_bf16"
        bf16_file = cache_dir / f"{fp8_path.stem}.bf16.safetensors"
        if not bf16_file.is_file() or bf16_file.stat().st_size < 1_000_000:
            _materialize_bfl_fp8_to_bf16(fp8_path, bf16_file)

        base_path = Path(base_model)
        print(f"[t2i] loading transformer from dequantized {bf16_file}", flush=True)
        if base_path.joinpath("transformer", "config.json").is_file():
            transformer = Flux2Transformer2DModel.from_single_file(
                str(bf16_file),
                config=str(base_path / "transformer"),
                torch_dtype=dtype,
            )
        else:
            transformer = Flux2Transformer2DModel.from_single_file(
                str(bf16_file),
                config=base_model,
                subfolder="transformer",
                torch_dtype=dtype,
            )
        if not (Path(pipe_id) / "model_index.json").is_file():
            pipe_id = base_model

    if not use_fp8:
        if Path(model).is_dir() and not _transformer_ready(model):
            raise FileNotFoundError(
                f"FLUX.2-klein BF16 transformer weights missing under {model}/transformer/. "
                "Download with: hf download black-forest-labs/FLUX.2-klein-4B "
                f"--include 'transformer/*' --local-dir {model}"
            )
        pipe_id = model

    print(f"[t2i] loading pipeline from {pipe_id}", flush=True)
    kwargs: dict = {"torch_dtype": dtype}
    if transformer is not None:
        kwargs["transformer"] = transformer
    pipe = Flux2KleinPipeline.from_pretrained(pipe_id, **kwargs)

    if offload:
        pipe.enable_model_cpu_offload()
    else:
        pipe.to(device)
    return pipe


def main() -> None:
    import torch

    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--width", type=int, default=768)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--steps", type=int, default=4)
    p.add_argument(
        "--model",
        default="black-forest-labs/FLUX.2-klein-4B",
        help="Full Diffusers pipeline (4B BF16) or local snapshot with model_index.json",
    )
    p.add_argument(
        "--fp8_transformer",
        default="",
        help="Optional BFL FP8 single-file (dequantized before load). Empty = BF16 only.",
    )
    p.add_argument(
        "--base_model",
        default="black-forest-labs/FLUX.2-klein-4B",
        help="BF16 pipeline used for text encoder / VAE when FP8 transformer is injected",
    )
    p.add_argument("--guidance_scale", type=float, default=1.0)
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--offload",
        action="store_true",
        help="CPU offload — frees VRAM between modules",
    )
    args = p.parse_args()

    prompt, negative = build_tpose_prompt(args.prompt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fp8 = (args.fp8_transformer or "").strip() or None
    meta = out.with_suffix(".prompt.txt")
    meta.write_text(
        f"user: {args.prompt}\nenhanced: {prompt}\nnegative: {negative}\n"
        f"model: {args.model}\nfp8_transformer: {fp8}\nbase: {args.base_model}\n"
        f"seed: {args.seed}\nsteps: {args.steps}\nguidance: {args.guidance_scale}\n"
        f"offload: {args.offload}\n",
        encoding="utf-8",
    )

    if not (
        _is_flux2_klein(args.model)
        or _is_flux2_klein(args.base_model)
        or (fp8 is not None and "klein" in fp8.lower())
    ):
        raise SystemExit(
            f"Only FLUX.2-klein is supported (got model={args.model!r}). "
            "SDXL-Turbo is disabled."
        )

    dtype = torch.bfloat16 if args.device.startswith("cuda") else torch.float32
    offload = args.offload
    if not offload and args.device.startswith("cuda"):
        try:
            free, _total = torch.cuda.mem_get_info()
            if free < 14 * 1024**3:
                offload = True
                print(f"[t2i] low free VRAM ({free/1024**3:.1f}GB) → CPU offload", flush=True)
        except Exception:
            pass

    print(f"[t2i] dtype={dtype} offload={offload} fp8={fp8}", flush=True)

    pipe = _load_flux2_klein(
        model=args.model,
        base_model=args.base_model,
        fp8_transformer=fp8,
        dtype=dtype,
        device=args.device,
        offload=offload,
    )
    gen_device = "cpu" if offload else args.device
    gen = torch.Generator(device=gen_device).manual_seed(args.seed)
    image = pipe(
        prompt=prompt,
        height=args.height,
        width=args.width,
        guidance_scale=args.guidance_scale,
        num_inference_steps=max(1, args.steps),
        generator=gen,
    ).images[0]

    image.save(out)
    print(f"saved {out}", flush=True)

    del pipe
    if args.device.startswith("cuda"):
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
