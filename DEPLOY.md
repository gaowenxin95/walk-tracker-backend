# 部署说明

这个项目可以作为一个 Python Web Service 部署。前端页面由后端根路径 `/` 返回，API 也在同一个服务里。

项目也支持 PWA。部署后用手机浏览器打开公网地址，可以添加到主屏幕，作为轻量手机 App 使用。

## 第一步：先上传到 GitHub

Render 和 Railway 都最适合从 GitHub 仓库部署。建议新建一个独立仓库，只放这个后端目录里的文件。

在 GitHub 创建一个空仓库，例如：

```text
walk-tracker-backend
```

然后本地执行：

```bash
cd "/Users/bytedance/Documents/New project 2/walk_tracker_backend"
git init
git add .
git commit -m "Initial walk tracker app"
git branch -M main
git remote add origin https://github.com/你的用户名/walk-tracker-backend.git
git push -u origin main
```

如果你选择把整个 `New project 2` 作为仓库推上去，那么部署平台里的 Root Directory 要填写：

```text
walk_tracker_backend
```

## 平台建议

### Render

适合先做演示版。

1. 打开 Render Dashboard
2. New > Web Service
3. 连接 GitHub，选择你的仓库
4. 如果仓库根目录就是这个项目，Root Directory 留空；如果仓库里有 `walk_tracker_backend` 子目录，Root Directory 填 `walk_tracker_backend`
5. Runtime 选 Python
6. Build Command：`python3 -m py_compile app.py`
7. Start Command：`python3 app.py`
8. Health Check Path：`/health`
9. Instance Type 先选 Free 或最低档
10. 点击 Create Web Service

部署完成后，你会拿到类似这样的 HTTPS 地址：

```text
https://walk-tracker-backend.onrender.com
```

打开这个地址就是前端页面，手机也可以用这个地址添加到主屏幕。

注意：免费 Web Service 的本地文件系统通常不是持久化的，SQLite 数据库文件可能会在重启、重新部署或休眠后丢失。正式保存用户数据时，需要换 PostgreSQL，或者使用付费持久化磁盘。

### Railway

适合继续使用 SQLite 的小项目。

1. 打开 Railway
2. New Project > Deploy from GitHub repo
3. 选择你的 GitHub 仓库
4. 如果仓库里有 `walk_tracker_backend` 子目录，Root Directory 填 `walk_tracker_backend`
5. Railway 会读取 `railway.toml`
6. Start Command 确认为：`python3 app.py`
7. Healthcheck Path 确认为：`/health`
8. 部署完成后，在 Networking / Public Networking 里生成公开域名

你会拿到类似这样的 HTTPS 地址：

```text
https://walk-tracker-production.up.railway.app
```

如果继续用 SQLite，需要给服务挂载 Volume。推荐把 Volume 挂到：

```text
/app/data
```

并设置环境变量：

```text
WALK_TRACKER_DB=/app/data/walk_records.sqlite3
```

不挂 Volume 也能跑，但重新部署或重启后，SQLite 数据可能会丢。

## 部署后检查

拿到 HTTPS 地址后，先检查：

```text
https://你的域名/health
```

应该返回：

```json
{"ok": true, "service": "walk-tracker-backend"}
```

然后打开：

```text
https://你的域名/
```

手机浏览器打开这个地址后，就可以添加到主屏幕。

### VPS

如果以后买任意云服务器，不限阿里云、腾讯云、AWS、DigitalOcean，都可以跑：

```bash
cd walk_tracker_backend
python3 app.py
```

生产环境建议再加 Nginx、HTTPS、进程守护和登录鉴权。

## 本地运行

```bash
cd walk_tracker_backend
python3 app.py
```

打开：

```text
http://127.0.0.1:8000/
```
