# Bilibili 视频下载器

基于 **FastAPI** + **yt-dlp** 的 Bilibili 视频下载网页工具。粘贴链接 → 选择分辨率 → 一键下载 MP4。

## 功能

- 输入 Bilibili 视频链接，自动获取标题、简介、封面图
- 支持选择分辨率：360p / 480p / 720p / 1080p
- 自动合并音视频流，输出 MP4 格式
- 实时显示下载进度和速度
- 浏览器直接操作，无需命令行

## 环境要求

- Python 3.8+
- ffmpeg
- 操作系统：Windows / macOS / Linux（WSL2 也可）

## 快速开始

### 1. 安装依赖

```bash
# 安装 ffmpeg
# macOS
brew install ffmpeg

# Ubuntu / Debian / WSL
sudo apt-get install ffmpeg

# Windows (choco)
choco install ffmpeg
```

```bash
# 安装 Python 依赖
pip install yt-dlp fastapi uvicorn aiohttp
```

### 2. 启动服务

```bash
cd bili-downloader
python3 main.py
```

或者使用启动脚本：

```bash
./start.sh
```

### 3. 打开网页

浏览器访问 **http://localhost:8899**

粘贴 Bilibili 视频 URL，点击「获取信息」，选择分辨率后点击「下载视频」即可。

## 项目结构

```
bili-downloader/
├── main.py          # FastAPI 后端服务
├── start.sh         # 启动脚本（自动检测 WSL2 IP）
├── static/
│   └── index.html   # 前端页面
└── downloads/       # 下载的视频存放目录（自动创建）
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/info?url=` | 获取视频信息和可用分辨率 |
| POST | `/api/download` | 启动下载任务 |
| GET | `/api/download/{task_id}/status` | 查询下载进度 |
| GET | `/api/download/{task_id}/file` | 下载完成后的文件 |

## 技术栈

- **后端**: FastAPI / yt-dlp / ffmpeg
- **前端**: 原生 HTML + CSS + JavaScript（无框架依赖）
