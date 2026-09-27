# AniLab

Game-ready image→3D SaaS:

**TripoSG** → **MV-Adapter** (4096 UV) → **UniRig** → skinned GLB

```
setup.sh          # uv venv + weight downloads
weights/          # model weights (gitignored)
saas/
  engines/        # TripoSG, MV-Adapter, UniRig
  inference/      # pipeline orchestration
  backend/        # FastAPI + GPU worker
  frontend/       # React / Vite
  storage/        # runtime uploads/outputs
```

## Setup

```bash
chmod +x setup.sh
./setup.sh
```

Creates `.venv` with **uv** if missing, syncs deps, downloads weights into `weights/`.

```bash
./setup.sh --weights-only   # download weights only
./setup.sh --force          # re-download
```

## Run

```bash
uv run main
uv run main --with-frontend
```

## CLI

```bash
source .venv/bin/activate
PYTHONPATH=. python -m saas.inference.pipeline \
  --image_path /path/to/image.png \
  --output_dir saas/storage/outputs \
  --output_name demo
```
