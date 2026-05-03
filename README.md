# Pixiv 图片下载器

一个带图形界面的 Pixiv 图片下载工具，支持单作品下载和画师批量下载。

## 功能

- **单作品下载** — 输入作品链接，下载全部页面
- **画师批量下载** — 输入画师主页链接，增量下载所有作品
- **Cookie 管理** — 内置 Cookie 粘贴和验证功能，登录后可以下载 R-18 内容
- **实时日志** — 下载过程实时显示，清晰看到进度和错误

## 使用方法

### 方式一：下载 exe（推荐）

1. 前往 [Releases](https://github.com/daosanmu-hub/pixiv-downloader-pixiv-/releases) 页面
2. 下载 `PixivDownloader.exe`
3. 双击运行

### 方式二：运行源码

需要 Python 3.10+

```bash
pip install requests
python pixiv_gui.py
```

或者双击 `pixiv_gui.bat`（会自动检测 Python）。

## 首次使用

1. 打开程序后，切换到 **「Cookie 管理」** 标签页
2. 按照 **「教程」** 标签页中的方法导出 Pixiv 的 Cookie JSON
3. 粘贴到 Cookie 管理页，点击 **「保存并验证」**
4. 切回 **「下载」** 标签页，输入作品或画师链接开始下载

## 项目结构

```
pixiv_gui.py          # 图形界面主程序
pixiv_download.py     # 下载引擎（也支持命令行使用）
pixiv_gui.bat         # GUI 启动脚本
pixiv_download.bat    # 命令行启动脚本
```

## 许可证

MIT
