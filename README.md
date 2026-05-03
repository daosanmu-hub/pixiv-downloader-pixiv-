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

## 更新说明

### v1.0.1 (2026-05-03)

- 修复 PyInstaller 打包后 exe 移动位置崩溃的问题
- 修复 `--windowed` 模式下日志不显示下载进度的问题
- 改进 403 错误提示，区分"未设置 Cookie"和"Cookie 已失效"
- 优化无 Cookie 时的下载提示信息

### v1.0.0

- 初始版本发布
- 支持单作品和画师批量下载
- 内置 Cookie 管理、验证和教程

## 致谢

本工具由 **深度求索 DeepSeek-V4-Pro** 辅助开发。

## 项目结构

```
pixiv_gui.py          # 图形界面主程序
pixiv_download.py     # 下载引擎（也支持命令行使用）
pixiv_gui.bat         # GUI 启动脚本
pixiv_download.bat    # 命令行启动脚本
```

## 许可证

MIT
