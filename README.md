# Bilibili 视频下载器

基于 **FastAPI** + **yt-dlp** 的 Bilibili / YouTube 视频下载网页工具。粘贴链接 → 选择分辨率 → 一键下载 MP4。

## 功能

- 支持 Bilibili 和 YouTube 视频下载
- 自动获取视频标题、简介、封面图
- 支持选择分辨率：360p / 480p / 720p / 1080p / 1440p / 2160p
- 支持批量下载
- 自动合并音视频流，输出 MP4 格式
- 实时显示下载进度和速度
- 浏览器直接操作，无需命令行
- 支持上传 Cookies 下载高清/付费视频
- 自动检测 WSL2 代理，无需手动配置

## 环境要求

- Python 3.8+
- ffmpeg（音视频合并必需）
- 操作系统：Windows / macOS / Linux（含 WSL2）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/cooleye/bili-downloader.git
cd bili-downloader
```

### 2. 创建虚拟环境

**Linux / macOS / WSL2:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

先安装系统级依赖 ffmpeg：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian / WSL2
sudo apt-get update && sudo apt-get install -y ffmpeg

# Windows (choco)
choco install ffmpeg

# Windows (winget)
winget install ffmpeg
```

再安装 Python 依赖：

```bash
# 确保虚拟环境已激活
pip install -r requirements.txt
```

### 4. 启动服务

```bash
python3 main.py
```

或使用启动脚本（自动检测 WSL2 IP 和代理端口）：

```bash
./start.sh
```

停止服务：

```bash
./stop.sh
```

### 5. 打开网页

浏览器访问 **http://localhost:8899**

- 粘贴视频链接，点击「获取信息」
- 选择分辨率
- 点击「下载视频」

## 项目结构

```
bili-downloader/
├── main.py              # FastAPI 后端服务（主入口）
├── requirements.txt     # Python 依赖列表
├── start.sh             # 启动脚本（自动检测 WSL2 代理）
├── stop.sh              # 停止服务脚本
├── .gitignore           # Git 忽略规则
├── static/
│   └── index.html       # 前端页面
└── downloads/           # 下载目录（自动创建）
    └── .gitkeep
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端页面 |
| GET | `/api/info?url=` | 获取视频信息和可用分辨率 |
| POST | `/api/download` | 启动下载任务 |
| GET | `/api/download/{task_id}/status` | 查询下载进度 |
| GET | `/api/download/{task_id}/file` | 获取已完成的文件 |
| POST | `/api/cookies` | 上传 Cookies |
| GET | `/api/cookies` | 查看 Cookies 状态 |
| DELETE | `/api/cookies` | 删除 Cookies |

## 常见问题

### 下载报错 / 获取信息失败

1. 升级 yt-dlp 到最新版：`pip install --upgrade yt-dlp`
2. 部分 Bilibili 高清视频需要 Cookies，在页面右上角上传 `cookies.txt`
3. 如果在 WSL2 中，确保 Windows 端代理已开启（脚本会自动检测）

### 如何获取 cookies.txt

使用浏览器插件导出 Netscape 格式的 cookies：

- Chrome / Edge：[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- Firefox：[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

导出 bilibili.com 的 cookies 后，在页面右上角上传即可。

### 换电脑后如何继续开发

```bash
# 1. 克隆项目
git clone https://github.com/cooleye/bili-downloader.git
cd bili-downloader

# 2. 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 安装系统依赖（Ubuntu / Debian / WSL2）
sudo apt-get install -y ffmpeg

# 5. 启动
python3 main.py
```

## 技术栈

- **后端**: FastAPI / yt-dlp / ffmpeg / uvicorn
- **前端**: 原生 HTML + CSS + JavaScript（无框架依赖）
