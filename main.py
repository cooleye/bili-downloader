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
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import yt_dlp
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = BASE_DIR / "downloads"
COOKIES_FILE = BASE_DIR / "cookies.txt"
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
    "no_check_certificate": True,
    "http_headers": {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    },
}

# Proxy: env var or auto-detect
_proxy = os.environ.get("YT_DLP_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
if not _proxy:
    proxy_ports = (7890, 7891, 1080, 7897)
    # Try localhost first (mirrored WSL2), then gateway IP
    targets = ["127.0.0.1"]
    try:
        gw = subprocess.run(
            ["ip", "route"], capture_output=True, text=True, timeout=3
        ).stdout
        m = re.search(r"default via (\S+)", gw)
        if m:
            targets.append(m.group(1))
    except Exception:
        pass
    for host in targets:
        for port in proxy_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                _proxy = f"http://{host}:{port}"
                sock.close()
                break
            sock.close()
        if _proxy:
            break

if _proxy:
    YDL_BASE["proxy"] = _proxy

# Clean old files (>24h) on startup
now = time.time()
for f in DOWNLOAD_DIR.iterdir():
    if f.is_file() and f.stat().st_mtime < now - 86400:
        f.unlink()


def safe_name(s: str, maxlen: int = 80) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s)[:maxlen].strip()


def clean_url(url: str) -> str:
    """Strip playlist/index params from YouTube URLs."""
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        qs = parse_qs(parsed.query)
        qs.pop("list", None)
        qs.pop("index", None)
        qs.pop("si", None)
        new_qs = urlencode(qs, doseq=True)
        parsed = parsed._replace(query=new_qs)
    return urlunparse(parsed)


# ── Frontend ──

@app.get("/")
def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text("utf-8"))


# ── Cookies ──

@app.post("/api/cookies")
async def upload_cookies(file: UploadFile = File(...)):
    content = await file.read()
    COOKIES_FILE.write_bytes(content)
    return {"success": True, "name": file.filename}

@app.get("/api/cookies")
def get_cookies_status():
    return {"exists": COOKIES_FILE.exists(), "name": COOKIES_FILE.name if COOKIES_FILE.exists() else ""}

@app.delete("/api/cookies")
def delete_cookies():
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
    return {"success": True}


# ── Video Info ──

def _extract_info(url, extra_opts=None):
    """Try with cookies, fall back to without if cookies are broken."""
    opts = {**YDL_BASE, **(extra_opts or {})}
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download="format" in opts)
    except Exception:
        if COOKIES_FILE.exists():
            opts.pop("cookiefile", None)
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download="format" in opts)
        raise


@app.get("/api/info")
def get_info(url: str = Query(...)):
    """获取视频元数据和可用分辨率"""
    try:
        info = _extract_info(clean_url(url))
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
    save_dir: str = ""


@app.post("/api/download")
def start_download(req: DownloadReq):
    """启动下载任务"""
    task_id = uuid.uuid4().hex[:12]
    clean = clean_url(req.url)
    task = {
        "id": task_id,
        "url": clean,
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
        fmt = f"bestvideo[height<=?{max_h}]+bestaudio/best[height<=?{max_h}]/best"

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                dl = d.get("downloaded_bytes", 0)
                task["progress"] = round(dl / total * 100, 1) if total else 0
                task["speed"] = d.get("_speed_str", "")
            elif d["status"] == "finished":
                task["progress"] = 100
                task["status"] = "merging"

        output_dir = Path(req.save_dir) if req.save_dir else DOWNLOAD_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取标题
        try:
            info = _extract_info(clean)
            title = info.get("title", "video")
        except Exception as e:
            task["status"] = "error"
            task["error"] = f"获取信息失败: {e}"
            return

        safe_title = safe_name(title)
        expected_file = output_dir / f"{safe_title}_{req.resolution}.mp4"

        # 如果文件已存在，跳过下载
        if expected_file.exists():
            task["filename"] = str(expected_file)
            task["status"] = "completed"
            task["progress"] = 100
            return

        # 下载
        opts = {
            **YDL_BASE,
            "format": fmt,
            "outtmpl": str(expected_file.with_suffix(".%(ext)s")),
            "merge_output_format": "mp4",
            "throttled_rate": 100000000,
            "progress_hooks": [hook],
        }
        if COOKIES_FILE.exists():
            opts["cookiefile"] = str(COOKIES_FILE)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(clean, download=True)
            task["filename"] = str(expected_file)
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
