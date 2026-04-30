#!/usr/bin/env python3
"""Bilibili 视频下载器 - 后端"""

import os
import re
import socket
import subprocess
import time
import uuid
import threading
from pathlib import Path

import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Bilibili 视频下载器")
tasks: dict = {}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "http_headers": {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    },
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
        },
    },
}

# Proxy: env var or auto-detect WSL2 gateway
_proxy = os.environ.get("YT_DLP_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
if not _proxy:
    try:
        gw = subprocess.run(
            ["ip", "route"], capture_output=True, text=True, timeout=3
        ).stdout
        m = re.search(r"default via (\S+)", gw)
        if m:
            gw_ip = m.group(1)
            for port in (7891, 7890, 1080, 7897, 8080, 8899):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                if sock.connect_ex((gw_ip, port)) == 0:
                    _proxy = f"http://{gw_ip}:{port}"
                    sock.close()
                    break
                sock.close()
    except Exception:
        pass

if _proxy:
    YDL_BASE["proxy"] = _proxy

# Clean old files (>24h) on startup
now = time.time()
for f in DOWNLOAD_DIR.iterdir():
    if f.is_file() and f.stat().st_mtime < now - 86400:
        f.unlink()


def safe_name(s: str, maxlen: int = 80) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s)[:maxlen].strip()


# ── Frontend ──

@app.get("/")
def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text("utf-8"))


# ── Video Info ──

@app.get("/api/info")
def get_info(url: str = Query(...)):
    """获取视频元数据和可用分辨率"""
    try:
        with yt_dlp.YoutubeDL({**YDL_BASE}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(400, f"获取信息失败: {e}")

    available = set()
    for f in info.get("formats", []):
        v = f.get("vcodec")
        if v and v != "none":
            h = f.get("height", 0)
            if h <= 0:
                continue
            label = next((l for limit, l in [(360,"360p"),(480,"480p"),(720,"720p"),(1080,"1080p"),(1440,"1440p"),(2160,"2160p")] if h <= limit), f"{h}p")
            available.add(label)

    order = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
    formats = [r for r in order if r in available]
    extras = sorted(
        [r for r in available if r not in order],
        key=lambda x: int(x.rstrip("p")),
    )
    formats.extend(extras)

    return {
        "success": True,
        "data": {
            "title": info.get("title", ""),
            "description": (info.get("description", "") or "")[:1000],
            "thumbnail": (info.get("thumbnail", "") or "").replace("http://", "https://"),
            "duration": info.get("duration", 0),
            "formats": formats,
        },
    }


# ── Download ──

class DownloadReq(BaseModel):
    url: str
    resolution: str


@app.post("/api/download")
def start_download(req: DownloadReq):
    """启动下载任务"""
    task_id = uuid.uuid4().hex[:12]
    task = {
        "id": task_id,
        "url": req.url,
        "resolution": req.resolution,
        "status": "starting",
        "progress": 0.0,
        "speed": "",
        "filename": "",
        "error": "",
    }
    tasks[task_id] = task

    def worker():
        hmap = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}
        max_h = hmap.get(req.resolution, 720)
        fmt = f"bestvideo[height<={max_h}]+bestaudio/best[height<={max_h}]"

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                dl = d.get("downloaded_bytes", 0)
                task["progress"] = round(dl / total * 100, 1) if total else 0
                task["speed"] = d.get("_speed_str", "")
            elif d["status"] == "finished":
                task["progress"] = 100
                task["status"] = "merging"

        opts = {
            **YDL_BASE,
            "format": fmt,
            "outtmpl": str(DOWNLOAD_DIR / f"%(title)s_{task_id}.%(ext)s"),
            "merge_output_format": "mp4",
            "throttled_rate": 100000000,
            "progress_hooks": [hook],
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(req.url, download=True)
                title = info.get("title", "video")
                expected = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
                if expected.exists():
                    task["filename"] = str(expected)
                else:
                    for f in DOWNLOAD_DIR.iterdir():
                        if task_id in f.name:
                            task["filename"] = str(f)
                            break
                task["title"] = safe_name(title)
                task["status"] = "completed"
        except Exception as e:
            task["status"] = "error"
            task["error"] = str(e)

    threading.Thread(target=worker, daemon=True).start()
    return {"task_id": task_id}


@app.get("/api/download/{task_id}/status")
def get_status(task_id: str):
    """查询下载进度"""
    t = tasks.get(task_id)
    if not t:
        raise HTTPException(404, "任务不存在")
    return {
        "status": t["status"],
        "progress": t["progress"],
        "speed": t["speed"],
        "error": t["error"],
    }


@app.get("/api/download/{task_id}/file")
def get_file(task_id: str):
    """提供下载完成的文件"""
    t = tasks.get(task_id)
    if not t or t["status"] != "completed" or not t.get("filename"):
        raise HTTPException(400, "文件未就绪")
    fp = t["filename"]
    if not Path(fp).exists():
        raise HTTPException(404, "文件已被删除")
    fname = f"{t.get('title', 'video')}_{t['resolution']}.mp4"
    return FileResponse(fp, filename=safe_name(fname), media_type="video/mp4")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8899)
