# Repository Guidelines

## Stack

**TripoSG → MV-Adapter → UniRig** only. No AniGen / SF3D.

## Layout

```
setup.sh                 # uv venv + downloads weights/
weights/                 # HF + texture bake checkpoints
saas/engines/            # engine checkouts (.venv per engine)
saas/inference/          # orchestration
saas/backend/            # FastAPI worker
saas/frontend/           # Vite UI
```

## Setup / run

```bash
./setup.sh
uv run main
uv run main --with-frontend
```

Weights live in `weights/`; `setup.sh` symlinks them into engine expected paths.
