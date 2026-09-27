"""Background GPU workers: one thread per GPU (TripoSG → MV-Adapter → UniRig)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.models.db import Job, SessionLocal
from app.services.progress import (
    detect_stage,
    overall_progress,
    parse_tqdm,
    strip_ansi,
    write_progress,
)
from app.services import warmup as warmup_svc

log = logging.getLogger("anilab.worker")


class JobWorker:
    """Runs up to ``len(gpu_ids)`` jobs in parallel, one dedicated GPU each."""

    def __init__(self, gpu_ids: list[int] | None = None) -> None:
        self.gpu_ids = list(gpu_ids if gpu_ids is not None else settings.gpu_ids)
        if not self.gpu_ids:
            self.gpu_ids = [0]
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._claim_lock = threading.Lock()
        self._warmup_lock = threading.Lock()
        self._warmup_done: set[int] = set()

    def start(self) -> None:
        if any(t.is_alive() for t in self._threads):
            return
        self._reclaim_orphans()
        self._stop.clear()
        self._threads = []
        for gpu_id in self.gpu_ids:
            t = threading.Thread(
                target=self._loop,
                args=(gpu_id,),
                name=f"yeetgen-gpu-{gpu_id}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)
        log.info(
            "GPU workers started: %s (max_concurrent=%s, warmup=%s)",
            self.gpu_ids,
            settings.max_concurrent_jobs,
            settings.warmup_on_startup,
        )

    def stop(self) -> None:
        self._stop.set()

    def _reclaim_orphans(self) -> None:
        """After API restart, any 'running' rows are abandoned — requeue them."""
        db = SessionLocal()
        try:
            orphans = db.query(Job).filter(Job.status == "running").all()
            for job in orphans:
                job.status = "queued"
                job.error = None
                job.started_at = None
                log.warning("requeued orphaned job %s after restart", job.id)
            if orphans:
                db.commit()
        finally:
            db.close()

    def request_warmup(self, force: bool = False) -> dict:
        """Queue a fresh warmup on each GPU (admin / health)."""
        if force:
            with self._warmup_lock:
                self._warmup_done.clear()
        for gpu_id in self.gpu_ids:
            threading.Thread(
                target=self._warmup_gpu,
                args=(gpu_id,),
                name=f"yeetgen-warmup-{gpu_id}",
                daemon=True,
            ).start()
        return warmup_svc.read_status()

    def _loop(self, gpu_id: int) -> None:
        log.info("worker ready on GPU %s", gpu_id)
        warmed = False
        while not self._stop.is_set():
            job_id = self._claim_next()
            if job_id is not None:
                try:
                    self._run_job(job_id, gpu_id=gpu_id)
                except Exception:
                    log.exception("job %s crashed on GPU %s", job_id, gpu_id)
                continue
            # Warm only when the queue is empty so orphans / user jobs aren't blocked
            if settings.warmup_on_startup and not warmed:
                warmed = True
                self._warmup_gpu(gpu_id)
                continue
            time.sleep(1.0)

    def _claim_next(self) -> int | None:
        with self._claim_lock:
            db = SessionLocal()
            try:
                running = db.query(Job).filter(Job.status == "running").count()
                if running >= settings.max_concurrent_jobs:
                    return None
                job = (
                    db.query(Job)
                    .filter(Job.status == "queued")
                    .order_by(Job.id.asc())
                    .first()
                )
                if job is None:
                    return None
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                db.commit()
                return job.id
            finally:
                db.close()

    def _fail(self, job_id: int, message: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = message[:4000]
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()
        out = settings.output_dir / f"job_{job_id}"
        write_progress(
            out / "progress.json",
            {
                "status": "failed",
                "overall_pct": 100.0,
                "eta_s": 0,
                "error": message[:500],
            },
        )

    def _prepare_image(
        self, mode: str, prompt: str | None, input_path: str | None, seed: int, out_dir: Path
    ) -> Path:
        if mode == "image":
            if not input_path or not Path(input_path).is_file():
                raise RuntimeError("Missing input image")
            return Path(input_path)
        if mode != "text":
            raise RuntimeError(f"Unsupported mode for image prep: {mode}")
        if not prompt:
            raise RuntimeError("Missing text prompt")

        # --- Stage 1: Text → Image ---
        from app.services.text_to_image import enhance_prompt_for_3d, generate_image

        log_path = out_dir / "worker.log"
        dest = out_dir / "t2i_image.png"
        asset_preview = out_dir / "asset" / "t2i_image.png"
        asset_preview.parent.mkdir(parents=True, exist_ok=True)

        self._append_log(log_path, "[stage 1/2] Text → Image (reference for 3D)")
        self._append_log(log_path, f"[t2i] user prompt: {prompt.strip()}")
        try:
            self._append_log(log_path, f"[t2i] enhanced: {enhance_prompt_for_3d(prompt)}")
        except Exception:
            pass
        write_progress(
            out_dir / "progress.json",
            {
                "status": "running",
                "mode": "text",
                **overall_progress(mode="text", stage="t2i", stage_pct=5.0, stage_eta_s=None),
                "message": "Stage 1/2: text → image…",
            },
        )
        generate_image(prompt, dest, seed=seed)
        # Keep a copy next to pipeline outputs for the UI / debugging
        try:
            import shutil

            shutil.copy2(dest, asset_preview)
        except Exception:
            pass
        self._append_log(
            log_path,
            f"[stage 1/2] Text → Image done → {dest} ({dest.stat().st_size} bytes)",
        )
        self._append_log(log_path, "[stage 2/2] Image → 3D (TripoSG → MV-Adapter → UniRig)")
        write_progress(
            out_dir / "progress.json",
            {
                "status": "running",
                "mode": "text",
                **overall_progress(mode="text", stage="t2i", stage_pct=100.0, stage_eta_s=0),
                "message": "Stage 2/2: image → 3D…",
                "t2i_image": str(dest),
            },
        )
        return dest

    def _pipeline_env(self, gpu_id: int) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = str(settings.repo_root) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        env["ANILAB_WEIGHTS"] = str(settings.repo_root / "weights")
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        env["ANILAB_GPU_ID"] = str(gpu_id)
        env["TQDM_MININTERVAL"] = "0.5"
        # Avoid TQDM_ASCII — with piped stdout it can ZeroDivisionError in hf/tqdm bars.
        env.pop("TQDM_ASCII", None)
        env["TQDM_NCOLS"] = "100"
        env["COLUMNS"] = "100"
        env["TERM"] = env.get("TERM") or "xterm-256color"
        # Weights are already under weights/; don't need HF progress spam
        env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        env["HF_HUB_OFFLINE"] = env.get("HF_HUB_OFFLINE", "0")
        if settings.xai_api_key and "XAI_API_KEY" not in env:
            env["XAI_API_KEY"] = settings.xai_api_key
        return env

    def _append_log(self, log_path: Path, text: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
            f.flush()

    def _run_streaming(
        self,
        cmd: list[str],
        *,
        cwd: str,
        env: dict[str, str],
        log_path: Path,
        progress_path: Path,
        mode: str,
        timeout: int,
        initial_stage: str | None = None,
    ) -> int:
        """Stream child stdout (incl. tqdm ``\\r``) into worker.log + progress.json."""
        self._append_log(log_path, f"$ {' '.join(cmd)}")
        stage = initial_stage
        stage_pct: float | None = None
        stage_eta: float | None = None
        last_write = 0.0

        def flush_progress(message: str | None = None) -> None:
            nonlocal last_write
            payload = {
                "status": "running",
                "mode": mode,
                **overall_progress(
                    mode=mode, stage=stage, stage_pct=stage_pct, stage_eta_s=stage_eta
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if message:
                payload["message"] = message
            write_progress(progress_path, payload)
            last_write = time.time()

        flush_progress("Starting pipeline…")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        assert proc.stdout is not None
        deadline = time.time() + timeout
        buf = b""
        try:
            while True:
                if time.time() > deadline:
                    proc.kill()
                    self._append_log(log_path, "[timeout] killed process")
                    return -1
                chunk = proc.stdout.read(256)
                if chunk:
                    buf += chunk
                    while True:
                        n = buf.find(b"\n")
                        r = buf.find(b"\r")
                        if n < 0 and r < 0:
                            break
                        if n >= 0 and (r < 0 or n < r):
                            line, buf = buf[:n], buf[n + 1 :]
                        else:
                            line, buf = buf[:r], buf[r + 1 :]
                            if buf.startswith(b"\n"):
                                buf = buf[1:]
                        text = strip_ansi(line.decode("utf-8", errors="replace").strip())
                        if not text:
                            continue
                        self._append_log(log_path, text)
                        stage = detect_stage(text, stage)
                        parsed = parse_tqdm(text)
                        if parsed:
                            stage_pct = parsed["pct"]
                            stage_eta = parsed["eta_s"]
                            flush_progress(text[:160])
                        elif time.time() - last_write > 2.0:
                            flush_progress(text[:160])
                elif proc.poll() is not None:
                    break
                else:
                    time.sleep(0.05)
            if buf.strip():
                text = strip_ansi(buf.decode("utf-8", errors="replace").strip())
                if text:
                    self._append_log(log_path, text)
            return int(proc.wait())
        except Exception:
            proc.kill()
            raise

    def _complete(self, job_id: int, glb: Path) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "completed"
                job.glb_path = str(glb)
                job.finished_at = datetime.now(timezone.utc)
                job.error = None
                db.commit()
            log.info("job %s completed -> %s", job_id, glb)
        finally:
            db.close()
        write_progress(
            settings.output_dir / f"job_{job_id}" / "progress.json",
            {
                "status": "completed",
                "overall_pct": 100.0,
                "eta_s": 0,
                "message": "Done",
            },
        )

    def _warmup_gpu(self, gpu_id: int) -> None:
        with self._warmup_lock:
            if gpu_id in self._warmup_done:
                return
            self._warmup_done.add(gpu_id)

        out_dir = settings.output_dir / f"warmup_gpu_{gpu_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / "worker.log"
        progress_path = out_dir / "progress.json"
        asset_dir = out_dir / "asset"
        t0 = time.perf_counter()
        warmup_svc.mark_gpu(gpu_id, state="running", started_at=datetime.now(timezone.utc).isoformat())
        self._append_log(log_path, f"[warmup] GPU {gpu_id} starting auto warm-up")

        try:
            image = warmup_svc.warmup_image()
            env = self._pipeline_env(gpu_id)
            cmd = [
                str(settings.pipeline_python),
                "-m",
                "saas.inference.pipeline",
                "--image_path",
                str(image),
                "--output_dir",
                str(out_dir),
                "--output_name",
                "asset",
                "--seed",
                "0",
                "--faces",
                str(settings.warmup_faces),
                "--triposg_steps",
                str(settings.warmup_triposg_steps),
                "--device",
                "cuda",
            ]
            code = self._run_streaming(
                cmd,
                cwd=str(settings.repo_root),
                env=env,
                log_path=log_path,
                progress_path=progress_path,
                mode="image",
                timeout=60 * 90,
                initial_stage="shape",
            )
            glb = asset_dir / "mesh.glb"
            elapsed = round(time.perf_counter() - t0, 1)
            if code != 0 or not glb.is_file():
                raise RuntimeError(f"warmup exit {code}; missing {glb}")
            warmup_svc.mark_gpu(
                gpu_id,
                state="ready",
                elapsed_s=elapsed,
                glb=str(glb),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            write_progress(
                progress_path,
                {"status": "completed", "overall_pct": 100.0, "eta_s": 0, "message": "Warmup ready"},
            )
            self._append_log(log_path, f"[warmup] GPU {gpu_id} ready in {elapsed}s")
            log.info("warmup GPU %s ready in %ss", gpu_id, elapsed)
        except Exception as exc:
            warmup_svc.mark_gpu(
                gpu_id,
                state="failed",
                error=str(exc)[:500],
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            self._append_log(log_path, f"[warmup] FAILED: {exc}")
            log.exception("warmup failed on GPU %s", gpu_id)
            # Allow retry later
            with self._warmup_lock:
                self._warmup_done.discard(gpu_id)

    def _run_job(self, job_id: int, *, gpu_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if job is None:
                return
            out_dir = settings.output_dir / f"job_{job_id}"
            out_dir.mkdir(parents=True, exist_ok=True)
            job.output_dir = str(out_dir)
            db.commit()
            mode = job.mode
            seed = job.seed
            prompt = job.prompt
            input_path = job.input_path
            asset_type = getattr(job, "asset_type", None) or settings.asset_type
        finally:
            db.close()

        asset_dir = out_dir / "asset"
        log_path = out_dir / "worker.log"
        progress_path = out_dir / "progress.json"
        env = self._pipeline_env(gpu_id)
        self._append_log(
            log_path, f"[worker] job={job_id} mode={mode} asset_type={asset_type} gpu={gpu_id}"
        )

        # Resume / short-circuit from existing artifacts after a crash/restart
        final_glb = asset_dir / "mesh.glb"
        textured = asset_dir / "asset_i2tex_shaded.glb"
        mesh_raw = asset_dir / "mesh_raw.glb"
        if final_glb.is_file():
            self._append_log(log_path, "[resume] mesh.glb already present — completing")
            self._complete(job_id, final_glb)
            return
        textured_alt = asset_dir / "asset_textured.glb"
        if mode != "rig" and asset_type == "prop" and (
            textured.is_file() or textured_alt.is_file()
        ):
            src = textured if textured.is_file() else textured_alt
            shutil.copy2(src, final_glb)
            self._append_log(log_path, f"[resume] prop textured mesh — skip rig: {src}")
            self._complete(job_id, final_glb)
            return
        if mode != "rig" and textured.is_file():
            self._append_log(log_path, f"[resume] textured mesh found — UniRig only: {textured}")
            mode = "rig"
            input_path = str(textured)
        elif mode != "rig" and mesh_raw.is_file():
            self._append_log(
                log_path,
                f"[resume] mesh_raw.glb found — skip TripoSG, continue texture+rig: {mesh_raw}",
            )
            # Keep image mode but tell pipeline via env to skip shape (handled below)
            env["ANILAB_RESUME_MESH_RAW"] = str(mesh_raw)

        write_progress(
            progress_path,
            {
                "status": "running",
                "mode": mode,
                **overall_progress(mode=mode, stage=None, stage_pct=None, stage_eta_s=None),
                "message": f"Claimed GPU {gpu_id}",
            },
        )

        if mode == "rig":
            if not input_path or not Path(input_path).is_file():
                self._fail(job_id, "Missing input mesh")
                return
            cmd = [
                str(settings.pipeline_python),
                "-m",
                "saas.inference.pipeline",
                "--rig-only",
                "--mesh_path",
                str(input_path),
                "--output_dir",
                str(out_dir),
                "--output_name",
                "asset",
                "--seed",
                str(seed),
                "--faces",
                str(settings.faces),
                "--device",
                "cuda",
            ]
            initial_stage = "rig"
        else:
            try:
                image_path = self._prepare_image(mode, prompt, input_path, seed, out_dir)
            except Exception as exc:
                self._fail(job_id, f"Input prep failed: {exc}")
                return

            if mode == "text":
                db = SessionLocal()
                try:
                    job = db.get(Job, job_id)
                    if job:
                        job.input_path = str(image_path)
                        db.commit()
                finally:
                    db.close()

            # bench_image 1:1 — TripoSG 35k/50 → MV-Adapter i2tex → UniRig
            cmd = [
                str(settings.pipeline_python),
                "-m",
                "saas.inference.pipeline",
                "--image_path",
                str(image_path),
                "--output_dir",
                str(out_dir),
                "--output_name",
                "asset",
                "--seed",
                str(seed),
                "--asset_type",
                asset_type,
                "--faces",
                str(settings.faces),
                "--triposg_steps",
                str(settings.triposg_steps),
                "--texture_backend",
                str(settings.texture_backend),
                "--texture_text",
                str(settings.texture_text),
                "--texture_steps",
                str(settings.texture_steps),
                "--texture_guidance",
                str(settings.texture_guidance),
                "--texture_uv_size",
                str(settings.texture_uv_size),
                "--device",
                "cuda",
            ]
            if settings.texture_preprocess_mesh:
                cmd.append("--texture_preprocess_mesh")
            else:
                cmd.append("--no-texture_preprocess_mesh")

            rebake_file = asset_dir / "rebake_options.json"
            if rebake_file.is_file():
                try:
                    import json
                    rebake_opts = json.loads(rebake_file.read_text())
                    if "rotation_yaw" in rebake_opts:
                        cmd.extend(["--rotation_yaw", str(rebake_opts["rotation_yaw"])])
                    if "rotation_pitch" in rebake_opts:
                        cmd.extend(["--rotation_pitch", str(rebake_opts["rotation_pitch"])])
                    if "uv_size" in rebake_opts:
                        for idx, item in enumerate(cmd):
                            if item == "--texture_uv_size" and idx + 1 < len(cmd):
                                cmd[idx + 1] = str(rebake_opts["uv_size"])
                    if "inpaint_mode" in rebake_opts:
                        cmd.extend(["--inpaint_mode", str(rebake_opts["inpaint_mode"])])
                    if "steps" in rebake_opts:
                        for idx, item in enumerate(cmd):
                            if item == "--texture_steps" and idx + 1 < len(cmd):
                                cmd[idx + 1] = str(rebake_opts["steps"])
                    if "guidance" in rebake_opts:
                        for idx, item in enumerate(cmd):
                            if item == "--texture_guidance" and idx + 1 < len(cmd):
                                cmd[idx + 1] = str(rebake_opts["guidance"])
                    self._append_log(log_path, f"[rebake] Applied custom UV/rotation options: {rebake_opts}")
                except Exception as e:
                    self._append_log(log_path, f"[rebake] Warning reading rebake_options.json: {e}")

            initial_stage = "shape"

        log.info("running job %s on GPU %s", job_id, gpu_id)
        code = self._run_streaming(
            cmd,
            cwd=str(settings.repo_root),
            env=env,
            log_path=log_path,
            progress_path=progress_path,
            mode=mode,
            timeout=60 * 90,
            initial_stage=initial_stage,
        )
        glb = asset_dir / "mesh.glb"
        if code != 0 or not glb.is_file():
            self._fail(
                job_id,
                f"Generation failed (exit {code}) on GPU {gpu_id}. See worker.log.",
            )
            return
        self._complete(job_id, glb)


worker = JobWorker()
