#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pixiv 图片下载器 - 桌面 GUI 版
"""

import sys
import os
import json
import threading
import queue
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox

SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pixiv_download as dl


# ============================================================
# stdout 重定向
# ============================================================
class StdoutRedirector:
    def __init__(self, q):
        self.q = q
        self._s = sys.stdout
    def write(self, t):
        self._s.write(t); self._s.flush(); self.q.put(t)
    def flush(self):
        self._s.flush()

class StdoutCtx:
    def __init__(self, r):
        self.r = r
    def __enter__(self):
        self._o = sys.stdout; sys.stdout = self.r; return self
    def __exit__(self, *a):
        sys.stdout = self._o


# ============================================================
# 调色板 & 样式
# ============================================================
class Colors:
    BG        = "#f5f5f7"   # 窗口背景
    CARD      = "#ffffff"   # 卡片背景
    BORDER    = "#e0e0e0"   # 边框
    ACCENT    = "#4a90d9"   # 主色 蓝
    ACCENT2   = "#357abd"   # 主色深
    SUCCESS   = "#2e7d32"   # 绿色
    DANGER    = "#c62828"   # 红色
    WARN      = "#e65100"   # 橙色
    TEXT      = "#333333"   # 正文
    MUTED     = "#888888"   # 辅助文字
    LOG_BG    = "#1a1a2e"   # 日志背景
    LOG_FG    = "#e0e0e0"   # 日志文字
    HEADER_BG = "#3a7bd5"   # 顶栏背景


def setup_styles():
    style = ttk.Style()
    available = style.theme_names()
    for t in ("clam", "alt", "vista", "default"):
        if t in available:
            style.theme_use(t)
            break

    # 全局默认
    style.configure(".", font=("Microsoft YaHei UI", 10), background=Colors.BG)
    style.configure("TFrame", background=Colors.BG)
    style.configure("TLabel", background=Colors.BG, foreground=Colors.TEXT)
    style.configure("TEntry", fieldbackground=Colors.CARD, foreground=Colors.TEXT,
                    borderwidth=1, padding=4)
    style.configure("TSpinbox", fieldbackground=Colors.CARD, foreground=Colors.TEXT,
                    borderwidth=1, padding=2)

    # 卡片
    style.configure("Card.TFrame", background=Colors.CARD, relief="solid", borderwidth=1)
    style.configure("Card.TLabel", background=Colors.CARD, foreground=Colors.TEXT)
    style.layout("Card.TFrame", [("Card.TFrame", {"sticky": "nswe", "border": "1",
        "children": [("Frame.border", {"sticky": "nswe", "border": "1",
            "children": [("Frame.padding", {"sticky": "nswe",
                "children": [("Frame", {"sticky": "nswe"})]
            })]
        })]
    })])

    # 标题
    style.configure("H1.TLabel", font=("Microsoft YaHei UI", 14, "bold"),
                    foreground=Colors.TEXT, background=Colors.CARD)
    style.configure("H2.TLabel", font=("Microsoft YaHei UI", 11, "bold"),
                    foreground=Colors.TEXT, background=Colors.BG)

    # 状态
    style.configure("Muted.TLabel", foreground=Colors.MUTED, background=Colors.BG)
    style.configure("Success.TLabel", foreground=Colors.SUCCESS, background=Colors.BG)
    style.configure("Danger.TLabel", foreground=Colors.DANGER, background=Colors.BG)

    # 按钮
    style.configure("TButton", font=("Microsoft YaHei UI", 10),
                    background=Colors.ACCENT, foreground="white",
                    borderwidth=0, focusthickness=0, padding=(16, 6))
    style.map("TButton",
              background=[("active", Colors.ACCENT2), ("disabled", "#b0b0b0")],
              foreground=[("disabled", "#666666")])

    # 辅助按钮
    style.configure("Sec.TButton", font=("Microsoft YaHei UI", 10),
                    background=Colors.CARD, foreground=Colors.TEXT,
                    borderwidth=1, relief="solid", focusthickness=0, padding=(12, 5))
    style.map("Sec.TButton",
              background=[("active", "#e8e8e8")])

    # 危险按钮
    style.configure("Danger.TButton", font=("Microsoft YaHei UI", 10),
                    background=Colors.DANGER, foreground="white",
                    borderwidth=0, focusthickness=0, padding=(12, 5))
    style.map("Danger.TButton",
              background=[("active", "#b71c1c"), ("disabled", "#b0b0b0")])

    # 日志区
    style.configure("LogFrame.TLabelFrame", background=Colors.BG)
    style.configure("LogFrame.TLabelFrame.Label", font=("Microsoft YaHei UI", 10, "bold"))

    return style


# ============================================================
# 主程序
# ============================================================
class PixivGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Pixiv 图片下载器")
        self.root.geometry("880x720")
        self.root.minsize(780, 600)
        self.root.configure(bg=Colors.BG)

        self.style = setup_styles()

        self.dl_url = StringVar()
        self.save_path = StringVar(value=str(dl.SAVE_FOLDER))
        self.cookie_status_str = StringVar(value="未检测")
        self.log_queue = queue.Queue()
        self._downloading = False

        self._build_header()
        self._build_body()
        self._poll_log()
        self._load_settings()
        self.root.after(500, self._refresh_cookie_status)

    # -----------------------------------------------------------
    # 顶栏
    # -----------------------------------------------------------
    def _build_header(self):
        h = Frame(self.root, bg=Colors.HEADER_BG, height=52)
        h.pack(fill=X)
        h.pack_propagate(False)

        Label(h, text="Pixiv 图片下载器", font=("Segoe UI", 15, "bold"),
              bg=Colors.HEADER_BG, fg="white").pack(side=LEFT, padx=18)

        # 状态标签放在顶栏右侧
        self._status_badge = Label(h, textvariable=self.cookie_status_str,
              font=("Microsoft YaHei UI", 9), bg=Colors.HEADER_BG, fg="#c8e6c9")
        self._status_badge.pack(side=RIGHT, padx=16)

        # 分隔线
        Frame(self.root, bg=Colors.BORDER, height=1).pack(fill=X)

    # -----------------------------------------------------------
    # 主体
    # -----------------------------------------------------------
    def _build_body(self):
        # ===== 标签页 =====
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=BOTH, expand=True, padx=16, pady=(12, 0))

        # ---------- 标签页 1: 下载 ----------
        f_dl = Frame(self.nb, bg=Colors.BG)
        self.nb.add(f_dl, text="  下载  ")

        # 卡片 1: URL
        c1 = Frame(f_dl, bg=Colors.CARD, relief="solid", borderwidth=1, highlightbackground=Colors.BORDER, highlightthickness=1)
        c1.pack(fill=X, padx=10, pady=(12, 8))

        Label(c1, text="Pixiv 链接", font=("Microsoft YaHei UI", 11, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(anchor=NW, padx=14, pady=(12, 4))
        Label(c1, text="支持: /artworks/12345  或  /users/12345",
              font=("Microsoft YaHei UI", 9), bg=Colors.CARD, fg=Colors.MUTED).pack(anchor=NW, padx=14, pady=(0, 8))

        url_row = Frame(c1, bg=Colors.CARD)
        url_row.pack(fill=X, padx=14, pady=(0, 12))
        e = ttk.Entry(url_row, textvariable=self.dl_url, font=("Segoe UI", 10))
        e.pack(side=LEFT, fill=X, expand=True, ipady=2)
        ttk.Button(url_row, text="粘贴", width=6, command=self._paste_url).pack(side=LEFT, padx=(8, 0))

        # 卡片 2: 保存 & 下载
        c2 = Frame(f_dl, bg=Colors.CARD, relief="solid", borderwidth=1, highlightbackground=Colors.BORDER, highlightthickness=1)
        c2.pack(fill=X, padx=10, pady=(0, 8))

        Label(c2, text="保存到", font=("Microsoft YaHei UI", 11, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(anchor=NW, padx=14, pady=(12, 8))

        save_row = Frame(c2, bg=Colors.CARD)
        save_row.pack(fill=X, padx=14, pady=(0, 12))
        e2 = ttk.Entry(save_row, textvariable=self.save_path, font=("Segoe UI", 10))
        e2.pack(side=LEFT, fill=X, expand=True, ipady=2)
        ttk.Button(save_row, text="浏览", width=6, command=self._browse_folder).pack(side=LEFT, padx=(8, 0))
        self.btn_dl = ttk.Button(save_row, text="开始下载", width=12, command=self._start_download)
        self.btn_dl.pack(side=LEFT, padx=(8, 0))

        # 卡片 3: 日志
        c3 = Frame(f_dl, bg=Colors.CARD, relief="solid", borderwidth=1, highlightbackground=Colors.BORDER, highlightthickness=1)
        c3.pack(fill=BOTH, expand=True, padx=10, pady=(0, 12))

        log_header = Frame(c3, bg=Colors.CARD)
        log_header.pack(fill=X, padx=14, pady=(12, 4))
        Label(log_header, text="日志", font=("Microsoft YaHei UI", 11, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(side=LEFT)
        ttk.Button(log_header, text="清除", style="Sec.TButton", width=6,
                   command=self._clear_log).pack(side=RIGHT)

        self.log = Text(c3, wrap=WORD, state=DISABLED, font=("Cascadia Code", 10),
                        bg=Colors.LOG_BG, fg=Colors.LOG_FG, insertbackground="white",
                        relief=FLAT, borderwidth=6, padx=8, pady=6)
        self.log.pack(fill=BOTH, expand=True, padx=12, pady=(4, 12))
        sc = ttk.Scrollbar(c3, orient=VERTICAL, command=self.log.yview)
        sc.place(in_=self.log, relx=1.0, rely=0, relheight=1.0, anchor=NE)
        self.log.config(yscrollcommand=sc.set)

        # ---------- 标签页 2: Cookie 管理 ----------
        self.f_cookie = Frame(self.nb, bg=Colors.BG)
        self.nb.add(self.f_cookie, text="  Cookie 管理  ")

        # Cookie 状态行
        ck_status_frame = Frame(self.f_cookie, bg=Colors.BG)
        ck_status_frame.pack(fill=X, padx=12, pady=(14, 6))
        Label(ck_status_frame, text="Cookie 状态:", font=("Microsoft YaHei UI", 10),
              bg=Colors.BG, fg=Colors.TEXT).pack(side=LEFT, padx=(0, 10))
        self.ck_status_label = Label(ck_status_frame, textvariable=self.cookie_status_str,
              font=("Microsoft YaHei UI", 10, "bold"), bg=Colors.BG)
        self.ck_status_label.pack(side=LEFT)
        ttk.Button(ck_status_frame, text="刷新", style="Sec.TButton", width=6,
                   command=lambda: [self._refresh_cookie_status(),
                     self.ck_status_label.configure(fg=Colors.SUCCESS if "有效" in self.cookie_status_str.get() else Colors.DANGER)]
                   ).pack(side=RIGHT)

        # Cookie JSON 卡片
        ck_card = Frame(self.f_cookie, bg=Colors.CARD, relief="solid", borderwidth=1,
                        highlightbackground=Colors.BORDER, highlightthickness=1)
        ck_card.pack(fill=BOTH, expand=True, padx=12, pady=6)

        Label(ck_card, text="粘贴 Cookie JSON", font=("Microsoft YaHei UI", 11, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(anchor=NW, padx=14, pady=(12, 8))

        self.ck_text = Text(ck_card, wrap=WORD, font=("Cascadia Code", 10), relief=FLAT,
                            bg="#fafafa", fg=Colors.TEXT, borderwidth=1, padx=10, pady=8)
        self.ck_text.pack(fill=BOTH, expand=True, padx=14, pady=(0, 6))
        self.ck_text.insert("1.0", '请将 Cookie JSON 粘贴到这里...\n\n[\n  {"name": "PHPSESSID", "value": "...", "domain": ".pixiv.net"}\n]')

        # Cookie 按钮行
        ck_btn_frame = Frame(self.f_cookie, bg=Colors.BG)
        ck_btn_frame.pack(fill=X, padx=12, pady=(6, 12))

        def save_cookie():
            raw = self.ck_text.get("1.0", END).strip()
            if not raw:
                messagebox.showwarning("提示", "请先粘贴 Cookie JSON")
                return
            try:
                data = json.loads(raw)
                if isinstance(data, str):
                    data = json.loads(data)
                if not isinstance(data, list):
                    raise ValueError("需要 JSON 数组格式")
                valid = [{"name": c["name"], "value": c["value"],
                          "domain": c.get("domain", ".pixiv.net")}
                         for c in data if isinstance(c, dict) and c.get("name") and c.get("value")]
                if not valid:
                    messagebox.showerror("错误", "未找到有效的 Cookie")
                    return
                with open(dl.COOKIE_FILE, "w", encoding="utf-8") as f:
                    json.dump(valid, f, indent=2, ensure_ascii=False)
                self._refresh_cookie_status()
                self.ck_status_label.configure(fg=Colors.SUCCESS)
                messagebox.showinfo("完成", f"已保存 {len(valid)} 个 Cookie\n并验证通过")
            except Exception as e:
                messagebox.showerror("解析失败", str(e))

        def clear_cookie():
            if messagebox.askyesno("确认", "确定清空所有 Cookie 吗？"):
                if dl.COOKIE_FILE.exists():
                    dl.COOKIE_FILE.unlink()
                self.cookie_status_str.set("无 Cookie")
                self._status_badge.configure(fg="#c8e6c9")
                self.ck_status_label.configure(fg=Colors.MUTED)

        ttk.Button(ck_btn_frame, text="保存并验证", command=save_cookie).pack(side=LEFT, padx=(0, 10))
        ttk.Button(ck_btn_frame, text="清空", style="Danger.TButton", command=clear_cookie).pack(side=LEFT)
        ttk.Button(ck_btn_frame, text="获取教程", style="Sec.TButton",
                   command=lambda: self.nb.select(self.f_tutorial)).pack(side=RIGHT)

        # ---------- 标签页 3: 教程 ----------
        self.f_tutorial = Frame(self.nb, bg=Colors.BG)
        self.nb.add(self.f_tutorial, text="  教程  ")

        # 容器带边距
        tc = Frame(self.f_tutorial, bg=Colors.BG)
        tc.pack(fill=BOTH, expand=True, padx=10, pady=12)

        # 标题
        Label(tc, text="如何获取 Pixiv Cookie", font=("Microsoft YaHei UI", 16, "bold"),
              bg=Colors.BG, fg=Colors.TEXT).pack(pady=(8, 4))
        Label(tc, text="将 Cookie 导出为 JSON 格式，粘贴到「Cookie 管理」中即可使用",
              font=("Microsoft YaHei UI", 10), bg=Colors.BG, fg=Colors.MUTED).pack(pady=(0, 14))

        # 教程内容卡片
        card = Frame(tc, bg=Colors.CARD, relief="solid", borderwidth=1,
                     highlightbackground=Colors.BORDER, highlightthickness=1)
        card.pack(fill=BOTH, expand=True)

        self.tutorial_text = Text(card, wrap=WORD, font=("Microsoft YaHei UI", 10), relief=FLAT,
                                  bg="#fafafa", fg=Colors.TEXT, padx=18, pady=14, borderwidth=0)
        self.tutorial_text.pack(fill=BOTH, expand=True, padx=1, pady=1)

        steps = """方法一：使用 EditThisCookie 插件（推荐）

1. 用 Chrome / Edge 打开 https://www.pixiv.net 并登录账号
2. 安装 EditThisCookie 浏览器扩展
3. 点击浏览器右上角的饼干图标
4. 点击左上角的「导出 / Export」按钮
5. 复制全部 JSON 文本
6. 粘贴到「Cookie 管理」中，点击「保存并验证」即可


方法二：手动从开发者工具导出

1. 在 Pixiv 页面按 F12 打开开发者工具
2. 切换到「应用 / Application」标签
3. 左侧展开 Cookies → 选择 www.pixiv.net
4. 任意 Cookie 上右键 → 全部显示
5. 选中所有行 → 复制 → 粘贴为 JSON
   （或使用 Cookie-Editor 插件导出）


方法三：使用浏览器书签脚本

1. 新建书签，网址填入以下代码：
   javascript:copy(document.cookie)
2. 在 Pixiv 页面点击该书签
3. 粘贴到本工具的 Cookie JSON 输入框


注意事项
• Cookie 通常 1-2 周过期，过期后需要重新导出
• 请勿将 Cookie 分享给他人，以免账号被盗
• 下载 R-18 内容必须使用有效的登录 Cookie"""

        self.tutorial_text.insert("1.0", steps)
        self.tutorial_text.config(state=DISABLED)

        # ===== 底部管理栏 =====
        foot = Frame(self.root, bg=Colors.BG)
        foot.pack(fill=X, padx=16, pady=(6, 10))

        ttk.Button(foot, text="Cookie 管理", command=lambda: self.nb.select(self.f_cookie)).pack(side=LEFT)
        ttk.Button(foot, text="设置", style="Sec.TButton", command=self._open_settings_dialog).pack(side=LEFT, padx=(8, 0))
        ttk.Button(foot, text="检查 Cookie", style="Sec.TButton", command=self._check_only).pack(side=LEFT, padx=(8, 0))
        ttk.Button(foot, text="教程", style="Sec.TButton",
                   command=lambda: self.nb.select(self.f_tutorial)).pack(side=LEFT, padx=(8, 0))

    # -----------------------------------------------------------
    # 辅助
    # -----------------------------------------------------------
    def _entry(self, e, parent):
        """给 Entry 加个轻微阴影效果"""
        pass

    def _paste_url(self):
        try:
            self.dl_url.set(self.root.clipboard_get())
        except Exception:
            pass

    def _browse_folder(self):
        d = filedialog.askdirectory(initialdir=self.save_path.get())
        if d:
            self.save_path.set(d)

    # -----------------------------------------------------------
    # 日志
    # -----------------------------------------------------------
    def _clear_log(self):
        self.log.config(state=NORMAL)
        self.log.delete("1.0", END)
        self.log.config(state=DISABLED)

    def _log_write(self, t):
        self.log.config(state=NORMAL)
        self.log.insert(END, t)
        self.log.see(END)
        self.log.config(state=DISABLED)

    def _poll_log(self):
        try:
            while True:
                self._log_write(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    # -----------------------------------------------------------
    # 设置窗口
    # -----------------------------------------------------------
    def _open_settings_dialog(self):
        w = Toplevel(self.root)
        w.title("设置")
        w.geometry("480x320")
        w.configure(bg=Colors.BG)
        w.transient(self.root)
        w.grab_set()
        w.resizable(False, False)

        sv = StringVar(value=self.save_path.get())
        da = DoubleVar(value=dl.REQUEST_DELAY)
        dp = DoubleVar(value=dl.PAGE_DELAY)

        # 路径
        pf = Frame(w, bg=Colors.CARD, relief="solid", borderwidth=1,
                   highlightbackground=Colors.BORDER, highlightthickness=1)
        pf.pack(fill=X, padx=16, pady=(16, 8))
        Label(pf, text="默认下载路径", font=("Microsoft YaHei UI", 10, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(anchor=NW, padx=12, pady=(10, 6))
        pr = Frame(pf, bg=Colors.CARD)
        pr.pack(fill=X, padx=12, pady=(0, 10))
        ttk.Entry(pr, textvariable=sv).pack(side=LEFT, fill=X, expand=True, ipady=2)
        ttk.Button(pr, text="浏览", style="Sec.TButton", width=6,
                   command=lambda: sv.set(filedialog.askdirectory(initialdir=sv.get()) or sv.get())).pack(side=LEFT, padx=(6, 0))

        # 延迟
        df = Frame(w, bg=Colors.CARD, relief="solid", borderwidth=1,
                   highlightbackground=Colors.BORDER, highlightthickness=1)
        df.pack(fill=X, padx=16, pady=8)
        Label(df, text="请求间隔（秒）", font=("Microsoft YaHei UI", 10, "bold"),
              bg=Colors.CARD, fg=Colors.TEXT).pack(anchor=NW, padx=12, pady=(10, 6))
        dr = Frame(df, bg=Colors.CARD)
        dr.pack(padx=12, pady=(0, 10))
        Label(dr, text="作品间隔:", bg=Colors.CARD, fg=Colors.TEXT).pack(side=LEFT)
        ttk.Spinbox(dr, from_=0.5, to=10, increment=0.5, textvariable=da, width=6).pack(side=LEFT, padx=(4, 16))
        Label(dr, text="图片间隔:", bg=Colors.CARD, fg=Colors.TEXT).pack(side=LEFT)
        ttk.Spinbox(dr, from_=0.3, to=10, increment=0.3, textvariable=dp, width=6).pack(side=LEFT, padx=(4, 0))

        # 应用
        def apply():
            p = sv.get()
            if p and os.path.isdir(p):
                self.save_path.set(p)
                dl.REQUEST_DELAY = da.get()
                dl.PAGE_DELAY = dp.get()
                self._save_settings_to_file()
                messagebox.showinfo("完成", "设置已保存")
                w.destroy()
            else:
                messagebox.showwarning("提示", "请选择有效的目录")

        ttk.Button(w, text="应用", command=apply).pack(pady=(8, 16))

    def _save_settings_to_file(self):
        sf = SCRIPT_DIR / "gui_settings.json"
        try:
            sf.write_text(json.dumps({
                "save_path": self.save_path.get(),
                "delay_artwork": dl.REQUEST_DELAY,
                "delay_page": dl.PAGE_DELAY,
            }, indent=2), "utf-8")
        except Exception:
            pass

    # -----------------------------------------------------------
    # Cookie 状态
    # -----------------------------------------------------------
    def _refresh_cookie_status(self):
        if dl.COOKIE_FILE.exists():
            dl.load_cookies()
            ok = dl.check_login()
            txt = "有效" if ok else "已失效"
            self.cookie_status_str.set(txt)
            self._status_badge.configure(fg="#c8e6c9" if ok else "#ffcdd2")
        else:
            self.cookie_status_str.set("无 Cookie")
            self._status_badge.configure(fg="#c8e6c9")

    def _check_only(self):
        if not dl.COOKIE_FILE.exists():
            messagebox.showwarning("Cookie", "请先设置 Cookie")
            return
        dl.load_cookies()
        ok = dl.check_login()
        self.cookie_status_str.set("有效" if ok else "已失效")
        if ok:
            messagebox.showinfo("Cookie", "Cookie 有效")
        else:
            if messagebox.askyesno("Cookie", "Cookie 已失效，现在更新吗？"):
                self.nb.select(self.f_cookie)

    # -----------------------------------------------------------
    # 下载
    # -----------------------------------------------------------
    def _start_download(self):
        if self._downloading:
            messagebox.showinfo("提示", "已有下载任务进行中")
            return

        url = self.dl_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先输入 URL")
            return

        result = dl.parse_url(url)
        if not result:
            messagebox.showerror("错误", "无法识别的 URL\n请使用 /artworks/ 或 /users/ 格式")
            return

        if not dl.COOKIE_FILE.exists():
            if not messagebox.askyesno("无 Cookie",
                    "未设置 Cookie，R-18 内容无法下载\n\n确定继续吗？"):
                return

        dl.load_cookies()
        self._downloading = True
        self.btn_dl.config(text="下载中...", state=DISABLED)
        self._clear_log()
        self._log_write(f">>> 开始下载: {url}\n{'='*55}\n")

        kind, item_id = result

        def worker():
            try:
                redir = StdoutRedirector(self.log_queue)
                with StdoutCtx(redir):
                    if kind == "artwork":
                        dl.download_artwork(item_id, self.save_path.get())
                    else:
                        dl.download_artist(item_id, self.save_path.get())
            finally:
                self.root.after(0, self._dl_done)

        threading.Thread(target=worker, daemon=True).start()

    def _dl_done(self):
        self._downloading = False
        self.btn_dl.config(text="开始下载", state=NORMAL)
        self._log_write(f"\n{'='*55}\n<<< 完成\n")

    # -----------------------------------------------------------
    # 设置持久化
    # -----------------------------------------------------------
    def _load_settings(self):
        sf = SCRIPT_DIR / "gui_settings.json"
        if not sf.exists():
            return
        try:
            s = json.loads(sf.read_text("utf-8"))
            if s.get("save_path") and os.path.isdir(s["save_path"]):
                self.save_path.set(s["save_path"])
            if "delay_artwork" in s:
                dl.REQUEST_DELAY = s["delay_artwork"]
            if "delay_page" in s:
                dl.PAGE_DELAY = s["delay_page"]
        except Exception:
            pass


# ============================================================
# 入口
# ============================================================
def main():
    root = Tk()
    app = PixivGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
