"""FFmpeg / FFprobe integration for the media engine.

Everything here is subprocess-driven. Long-running pipelines (ingest, record)
return a created `asyncio.subprocess.Process`; one-shot probes/captures run on
the caller's executor thread so the event loop is never blocked.
"""

import asyncio
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.core.config import settings

FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_BIN = shutil.which("ffprobe") or "ffprobe"

_SUPPORTED_H264_ENCODERS = (
    "h264_nvenc",
    "h264_vaapi",
    "h264_qsv",
    "h264_amf",
    "h264_videotoolbox",
    "h264",
)


@dataclass
class FfmpegAssets:
    """Detected runtime capabilities of the media engine host."""

    ffmpeg: bool = False
    ffprobe: bool = False
    version: str | None = None
    encoders: list[str] = field(default_factory=list)
    gpu: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ffmpeg": self.ffmpeg,
            "ffprobe": self.ffprobe,
            "version": self.version,
            "h264_encoder": "h264_nvenc" if self.gpu.get("backend") == "nvenc" else "libx264",
            "accelerated": bool(self.gpu.get("available")),
            "gpu": self.gpu,
        }


async def _run_async(cmd: list[str], *, timeout: float | None = None) -> tuple[int, str, str]:
    """Run a subprocess asynchronously; returns (code, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    except asyncio.TimeoutError:
        return -1, "", "timed out"
    except FileNotFoundError:
        return -1, "", "ffmpeg binary not found"
    except OSError as exc:  # pragma: no cover - defensive
        return -1, "", str(exc)


def _probe_sync(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


async def running_version(timeout: float = 5.0) -> str | None:
    code, out, _err = await _run_async([FFMPEG_BIN, "-version"], timeout=timeout)
    if code != 0:
        return None
    first = out.splitlines()[0] if out else ""
    return first.strip() or None


async def available_encoders(timeout: float = 5.0) -> list[str]:
    code, out, _err = await _run_async([FFMPEG_BIN, "-hide_banner", "-encoders"], timeout=timeout)
    if code != 0:
        return []
    found: list[str] = []
    for line in out.splitlines():
        match = re.match(r"\s*[VAS]=\s+(\S+)", line)
        if match and match.group(1) in _SUPPORTED_H264_ENCODERS:
            found.append(match.group(1))
    return found


async def detect_gpu() -> dict[str, Any]:
    """Detect usable GPU acceleration (auto mode). Local container has none."""
    if settings.GPU_ACCELERATION.lower() == "none":
        return {"available": False, "backend": None, "device": None}
    try:
        code, out, _err = await _run_async(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=4.0)
        if code == 0 and out.strip():
            return {"available": True, "backend": "nvenc", "device": out.strip().splitlines()[:1]}
    except Exception:
        pass
    return {"available": False, "backend": None, "device": None}


async def probe_media(source: str, *, extra_args: list[str] | None = None, timeout: float | None = None) -> dict[str, Any]:
    """Probe a media source with ffprobe. Returns the full JSON document."""
    timeout = timeout or (settings.FFMPEG_TIMEOUT_SECONDS * 2 + 5)
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-rtsp_transport", settings.RTSP_TRANSPORT,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(input_arguments(source))
    loop = asyncio.get_running_loop()
    proc = await loop.run_in_executor(None, lambda: _probe_sync(cmd, timeout))
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace")) if proc.stdout else {}
    except json.JSONDecodeError:
        data = {}
    return data


def _video_stream(probe: dict[str, Any]) -> dict[str, Any] | None:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def summarize_probe(probe: dict[str, Any]) -> dict[str, Any]:
    """Extract the human-facing essentials from a full ffprobe document."""
    video = _video_stream(probe)
    fmt = probe.get("format", {})
    if video is None:
        return {"ok": False, "message": "No video stream found in the media source."}
    fps = _parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    codec = video.get("codec_name")
    pix_fmt = video.get("pix_fmt")
    return {
        "ok": True,
        "codec": codec,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "pix_fmt": pix_fmt,
        "fps": fps,
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "duration": float(fmt.get("duration") or 0.0),
        "format": fmt.get("format_name"),
    }


def _parse_rate(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        try:
            num, den = value.split("/", 1)
            return round(float(num) / float(den), 3)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return round(float(value), 3)
    except ValueError:
        return 0.0


def _scale_filter(target: int) -> str:
    """Cap the longest edge at `target`, preserving aspect ratio."""
    return f"scale=-2:'min({target},ih)'"


def input_arguments(source: str) -> list[str]:
    """Return the `-i` position arguments for a source.

    Synthetic lavfi sources (e.g. ``lavfi:testsrc2=size=1280x720:rate=25``)
    are expressed as ``-f lavfi -i <graph>`` — the ``lavfi:`` pseudo-protocol
    is not resolved by every ffmpeg build.
    """
    if source.startswith("lavfi:"):
        return ["-f", "lavfi", "-i", source[len("lavfi:") :]]
    return ["-i", source]


def build_ingest_command(source: str, camera_id: UUID, *, scale: int, fps: int, crf: int, preset: str) -> list[str]:
    """One ffmpeg process per camera.

    Outputs:
      * RTSP publish to the edge server (HLS + WebRTC fan-out)
      * MJPEG on stdout (live preview, snapshots, motion sampling)
    """
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", "error",
        "-fflags", "nobuffer+genpts",
        "-analyzeduration", "500000",
        "-probesize", "2000000",
    ]
    if _is_rtsp_like(source):
        cmd += ["-rtsp_transport", settings.RTSP_TRANSPORT, "-timeout", str(int(settings.FFMPEG_TIMEOUT_SECONDS * 1_000_000))]
    elif _is_http_like(source):
        cmd += ["-rw_timeout", str(int(settings.FFMPEG_TIMEOUT_SECONDS * 1_000_000))]
    cmd += input_arguments(source)
    cmd += ["-an"]
    scale_filter = _scale_filter(scale)
    if scale_filter:
        cmd += ["-vf", scale_filter]
    gop = max(int(fps * 2), 2)
    cmd += [
        "-c:v", "libx264",
        "-preset", preset,
        "-tune", "zerolatency",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-g", str(gop),
        "-keyint_min", str(gop // 2),
        "-sc_threshold", "0",
        "-r", str(fps),
        "-f", "rtsp",
        "-rtsp_transport", settings.RTSP_TRANSPORT,
        f"{settings.MEDIAMTX_RTSP_URL.rstrip('/')}/sentinel/{camera_id}",
        "-c:v", "mjpeg",
        "-q:v", str(settings.MJPEG_QUALITY),
        "-f", "mjpeg",
        "pipe:1",
    ]
    return cmd


def build_recorder_command(input_source: str, output_path: str, *, seconds: int = 0, segment: int = 15) -> list[str]:
    """Continuous MP4 recorder. `seconds=0` records until the process is stopped."""
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", "error",
        "-fflags", "nobuffer+genpts",
    ]
    if _is_rtsp_like(input_source):
        cmd += ["-rtsp_transport", settings.RTSP_TRANSPORT]
    cmd += input_arguments(input_source)
    cmd += [
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+frag_keyframe+empty_moov+faststart",
    ]
    if seconds and seconds > 0:
        cmd += ["-t", str(seconds)]
    cmd += ["-y", output_path]
    return cmd


async def capture_snapshot(source: str, *, timeout: float | None = None) -> bytes | None:
    """Capture a single JPEG frame from a source (on-demand, no session required)."""
    timeout = timeout or (settings.FFMPEG_TIMEOUT_SECONDS + 4)
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", "error",
        "-fflags", "nobuffer+genpts",
    ]
    if _is_rtsp_like(source):
        cmd += ["-rtsp_transport", settings.RTSP_TRANSPORT, "-timeout", str(int(settings.FFMPEG_TIMEOUT_SECONDS * 1_000_000))]
    elif _is_http_like(source):
        cmd += ["-rw_timeout", str(int(settings.FFMPEG_TIMEOUT_SECONDS * 1_000_000))]
    cmd += input_arguments(source)
    cmd += [
        "-frames:v", "1",
        "-q:v", "3",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1",
    ]

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)

    loop = asyncio.get_running_loop()
    proc = await loop.run_in_executor(None, _run)
    if proc.returncode != 0 or not proc.stdout:
        return None
    return proc.stdout


def _is_rtsp_like(source: str) -> bool:
    return source.lower().startswith(("rtsp://", "rtsps://"))


def _is_http_like(source: str) -> bool:
    return source.lower().startswith(("http://", "https://", "hls://"))


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "FFMPEG_BIN",
    "FFPROBE_BIN",
    "build_ingest_command",
    "build_recorder_command",
    "capture_snapshot",
    "detect_gpu",
    "input_arguments",
    "probe_media",
    "running_version",
    "summarize_probe",
]