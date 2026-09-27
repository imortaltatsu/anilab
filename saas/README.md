# AniLab SaaS

TripoSG → MV-Adapter → UniRig. Backend, frontend, inference, and engines live here.

## Run

From repo root:

```bash
uv run main
uv run main --with-frontend
```

## Engines

| Path | Role |
|------|------|
| `engines/TripoSG` | Shape |
| `engines/MV-Adapter` | 4096 UV texture |
| `engines/UniRig` | Auto-rig |

Each engine uses its own `.venv`. Orchestration: `inference/pipeline.py`.
