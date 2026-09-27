# Model weights (gitignored)

Populated by `./setup.sh`:

| Path | Source |
|------|--------|
| `triposg/TripoSG` | `VAST-AI/TripoSG` |
| `triposg/RMBG-1.4` | `briaai/RMBG-1.4` |
| `mvadapter/*.pth` / `*.pt` | Real-ESRGAN + LaMa |
| `mvadapter/mv-adapter` | `huanngzh/mv-adapter` |
| `unirig/` | `VAST-AI/UniRig` |

Engine code under `saas/engines/*/ `symlinks into these dirs (see `setup.sh`).
