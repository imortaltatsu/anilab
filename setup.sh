#!/usr/bin/env bash
# AniLab setup: create .venv with uv (if missing) and download model weights.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Safe exit when sourced vs executed
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  _die() { return "$1"; }
else
  _die() { exit "$1"; }
fi

WEIGHTS="$ROOT/weights"
TRIPOSG_W="$WEIGHTS/triposg"
MV_W="$WEIGHTS/mvadapter"
UNIRIG_W="$WEIGHTS/unirig"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: '$1' is required but not installed" >&2
    _die 1
  }
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo "uv not found; installing…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  need_cmd uv
}

ensure_venv() {
  if [[ -d "$ROOT/.venv" && -x "$ROOT/.venv/bin/python" ]]; then
    echo "venv exists: $ROOT/.venv"
  else
    echo "creating venv with uv…"
    uv venv "$ROOT/.venv" --python 3.11
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  echo "syncing SaaS dependencies…"
  uv sync
}

link_engine_weights() {
  mkdir -p "$TRIPOSG_W" "$MV_W" "$UNIRIG_W"
  local eng="$ROOT/saas/engines"
  if [[ -d "$eng/TripoSG" ]]; then
    rm -rf "$eng/TripoSG/pretrained_weights"
    ln -sfn "$TRIPOSG_W" "$eng/TripoSG/pretrained_weights"
  fi
  if [[ -d "$eng/MV-Adapter" ]]; then
    rm -rf "$eng/MV-Adapter/checkpoints"
    ln -sfn "$MV_W" "$eng/MV-Adapter/checkpoints"
  fi
}

download_hf() {
  local repo="$1"
  local dest="$2"
  mkdir -p "$dest"
  # Consider present if dest has any file (not only empty dir)
  if [[ -n "$(find "$dest" -type f 2>/dev/null | head -1)" ]] && [[ "${FORCE_DOWNLOAD:-0}" != "1" ]]; then
    echo "skip (exists): $repo → $dest"
    return 0
  fi
  echo "download: $repo → $dest"
  if command -v hf >/dev/null 2>&1; then
    hf download "$repo" --local-dir "$dest"
  else
    "$ROOT/.venv/bin/python" -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='$repo', local_dir='$dest')
print('ok: $repo')
"
  fi
}

download_url() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]] && [[ "${FORCE_DOWNLOAD:-0}" != "1" ]]; then
    echo "skip (exists): $dest"
    return 0
  fi
  echo "download: $url"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 -o "$dest" "$url"
  else
    wget -O "$dest" "$url"
  fi
}

download_weights() {
  echo "=== downloading weights into $WEIGHTS ==="
  mkdir -p "$TRIPOSG_W" "$MV_W" "$UNIRIG_W"

  uv pip install --python "$ROOT/.venv/bin/python" "huggingface_hub>=0.24" >/dev/null

  download_hf "VAST-AI/TripoSG" "$TRIPOSG_W/TripoSG"
  download_hf "briaai/RMBG-1.4" "$TRIPOSG_W/RMBG-1.4"

  download_url \
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth" \
    "$MV_W/RealESRGAN_x2plus.pth"
  download_url \
    "https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt" \
    "$MV_W/big-lama.pt"
  download_hf "huanngzh/mv-adapter" "$MV_W/mv-adapter"

  download_hf "VAST-AI/UniRig" "$UNIRIG_W"

  link_engine_weights
  echo "weights ready:"
  du -sh "$TRIPOSG_W" "$MV_W" "$UNIRIG_W" 2>/dev/null || true
}

WEIGHTS_ONLY=0
FORCE_DOWNLOAD="${FORCE_DOWNLOAD:-0}"
for arg in "$@"; do
  case "$arg" in
    --weights-only) WEIGHTS_ONLY=1 ;;
    --force) FORCE_DOWNLOAD=1; export FORCE_DOWNLOAD=1 ;;
    -h|--help)
      cat <<EOF
Usage: ./setup.sh [--weights-only] [--force]

  (default)       create .venv with uv if missing, uv sync, download weights
  --weights-only  only download / link weights
  --force         re-download even if files exist
EOF
      _die 0
      ;;
    *) echo "unknown arg: $arg" >&2; _die 1 ;;
  esac
done

ensure_uv
if [[ "$WEIGHTS_ONLY" -eq 0 ]]; then
  ensure_venv
elif [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  ensure_venv
fi
download_weights

echo
echo "Done. Activate:  source .venv/bin/activate"
echo "Run:             uv run main"
echo "                 uv run main --with-frontend"
