#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pixiv 图片下载器 v3.2（支持 Cookie 登录态 + Cookie 配置）
支持：单作品页 / 画师主页（增量下载）
修复：画师下载改用 /ajax/illust/{id} 获取真实图片 URL
"""

import sys
import os
import re
import json
import time
import hashlib
import random
from pathlib import Path

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    print("[错误] 缺少 requests 库，请先运行: pip install requests")
    sys.exit(1)

# ------------------------------------------------------------
# 配置区
# ------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
COOKIE_FILE = SCRIPT_DIR / "pixiv_cookies.json"
SAVE_FOLDER = Path.home() / "Downloads" / "Pixiv_Images"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.pixiv.net/",
    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# 重试配置
MAX_RETRIES = 4
BASE_DELAY = 3
MAX_DELAY = 60
REQUEST_DELAY = 2.0   # 每件作品元数据请求间隔
PAGE_DELAY = 1.5      # 每张图片间隔


# ------------------------------------------------------------
# 重试工具
# ------------------------------------------------------------
def _is_retryable(exc):
    msg = str(exc).lower()
    retryable = [
        "connectionreseterror", "connection aborted",
        "connection reset by peer", "remote host closed",
        "timeout", "timed out", "temporarily unavailable",
        "rate limit", "service temporarily",
    ]
    return any(k in msg for k in retryable)


def requests_retry(method, url, *, retries=MAX_RETRIES, base_delay=BASE_DELAY,
                   raise_on_fail=True, **kwargs):
    kwargs.setdefault("timeout", 20)
    method_func = getattr(SESSION, method, SESSION.get)
    last_exc = None

    for attempt in range(retries):
        try:
            resp = method_func(url, **kwargs)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", base_delay * (2 ** attempt)))
                print(f"    [限速] HTTP 429，等待 {wait}s ...")
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600:
                raise RequestException(f"HTTP {resp.status_code}")
            return resp
        except RequestException as e:
            last_exc = e
            if not _is_retryable(e) and attempt >= retries - 2:
                if raise_on_fail:
                    raise
                return None
        except Exception as e:
            last_exc = e

        if attempt < retries - 1:
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 2), MAX_DELAY)
            print(f"    [重试] {attempt + 1}/{retries - 1}，{delay:.1f}s 后... ({last_exc})")
            time.sleep(delay)

    if raise_on_fail:
        raise last_exc
    return None


# ------------------------------------------------------------
# Cookie 管理
# ------------------------------------------------------------
def update_cookie():
    """交互式更新 Cookie"""
    print()
    print("=" * 50)
    print("  Cookie 配置")
    print("=" * 50)
    print()
    print("  请从浏览器导出 Cookie 为 JSON 格式后粘贴进来。")
    print("  输入完成后按 Ctrl+Z 回车 结束输入。")
    print("  输入 0 取消操作。")
    print()

    lines = []
    print("> ", end="", flush=True)
    try:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line.strip() == "0":
                print("已取消。")
                return
            lines.append(line)
            print("> ", end="", flush=True)
    except EOFError:
        pass

    raw = "\n".join(lines).strip()
    if not raw:
        print("[错误] 输入为空。")
        return

    try:
        cookies_data = json.loads(raw)
        if isinstance(cookies_data, str):
            cookies_data = json.loads(cookies_data)
        if not isinstance(cookies_data, list):
            raise ValueError("不是数组格式")
    except Exception as e:
        print(f"[错误] JSON 解析失败: {e}")
        return

    valid = [
        {"name": c["name"], "value": c["value"],
         "domain": c.get("domain", ".pixiv.net")}
        for c in cookies_data
        if isinstance(c, dict) and c.get("name") and c.get("value")
    ]

    if not valid:
        print("[错误] 没有找到有效的 Cookie 条目。")
        return

    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已保存 {len(valid)} 个 Cookie 到: {COOKIE_FILE}")
    print()
    print("  正在验证 Cookie 有效性...")
    SESSION2 = requests.Session()
    SESSION2.headers.update(HEADERS)
    for item in valid:
        if item["name"] in ("__cf_bm", "_cfuvid"):
            continue
        c = requests.cookies.create_cookie(
            domain=item.get("domain", ".pixiv.net"),
            name=item["name"], value=item["value"],
        )
        SESSION2.cookies.set_cookie(c)

    try:
        resp = requests_retry("get", "https://www.pixiv.net/ajax/illust/80624917",
                               retries=3, raise_on_fail=False)
        if resp and resp.status_code == 200:
            data = resp.json()
            if not data.get("error", False):
                print(f"  [OK] Cookie 有效，API连接正常")
                return
        print("  [!] Cookie 可能已失效")
    except Exception as e:
        print(f"  [!] 验证请求失败: {e}")


def clear_session_cookies():
    """清空 SESSION 中的 Cookie"""
    SESSION.cookies.clear()


def load_cookies():
    """从 JSON 文件加载 Cookie 到 SESSION"""
    if not COOKIE_FILE.exists():
        print(f"[警告] 未找到 Cookie 文件: {COOKIE_FILE}")
        print("  将以未登录状态访问，部分内容可能无法下载")
        return False

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies_data = json.load(f)

        clear_session_cookies()
        for item in cookies_data:
            name = item.get("name", "")
            value = item.get("value", "")
            if not name or not value:
                continue
            if name in ("__cf_bm", "_cfuvid", "__cf_bm_v2"):
                continue
            c = requests.cookies.create_cookie(
                domain=item.get("domain", ".pixiv.net"),
                name=name, value=value,
            )
            SESSION.cookies.set_cookie(c)

        print(f"[OK] 已加载 {len(cookies_data)} 个 Cookie 条目")
        return True
    except Exception as e:
        print(f"[错误] 加载 Cookie 失败: {e}")
        return False


def check_login():
    """检查 Cookie 是否有效（带重试）"""
    try:
        resp = requests_retry(
            "get",
            "https://www.pixiv.net/ajax/illust/80624917",
            retries=3,
            raise_on_fail=False,
        )
        if resp and resp.status_code == 200:
            data = resp.json()
            if not data.get("error", False):
                title = data.get("body", {}).get("title", "")
                if title:
                    print(f"[OK] Cookie 有效，API连接正常")
                    return True
        print("[!] Cookie 可能已失效")
        return False
    except Exception as e:
        print(f"[!] 网络错误: {e}")
        return False


# ------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------
def save_image(url: str, folder: str, filename: str = None) -> bool:
    """下载单张图片（带重试）"""
    Path(folder).mkdir(parents=True, exist_ok=True)

    if not filename:
        ext = os.path.splitext(url.split("?")[0].split("/")[-1])[-1]
        if not ext or len(ext) > 5:
            ext = ".jpg"
        filename = hashlib.md5(url.encode()).hexdigest()[:12] + ext

    filepath = os.path.join(folder, filename)
    if os.path.exists(filepath):
        print(f"    [跳过] {filename}")
        return True

    try:
        resp = requests_retry("get", url, retries=MAX_RETRIES)
        if resp is None:
            print(f"    [失败] {filename} (重试耗尽)")
            return False
        if resp.status_code == 403:
            print(f"    [失败] {filename} (403，需刷新Cookie)")
            return False
        if resp.status_code == 404:
            print(f"    [失败] {filename} (404，链接不存在)")
            return False
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        size = len(resp.content)
        print(f"    [下载] {filename} ({size // 1024} KB)")
        return True
    except Exception as e:
        print(f"    [失败] {filename}: {e}")
        return False


def get_artwork_metadata(work_id: str) -> dict:
    """
    获取单个作品的元数据（真实图片URL等）。
    优先从缓存获取，缓存miss则请求API。
    """
    url = f"https://www.pixiv.net/ajax/illust/{work_id}"
    resp = requests_retry("get", url, retries=MAX_RETRIES)
    resp.raise_for_status()
    return resp.json()


def parse_url(url: str):
    m = re.search(r"/artworks/(\d+)", url)
    if m:
        return ("artwork", m.group(1))
    m = re.search(r"/illust/(\d+)", url)
    if m:
        return ("artwork", m.group(1))
    m = re.search(r"/comics/(\d+)", url)
    if m:
        return ("artwork", m.group(1))
    m = re.search(r"/novel/(\d+)", url)
    if m:
        return ("novel", m.group(1))
    m = re.search(r"/users/(\d+)", url)
    if m:
        return ("artist", m.group(1))
    return None


# ------------------------------------------------------------
# 下载单作品
# ------------------------------------------------------------
def download_artwork(work_id: str, folder: str):
    print(f"\n[作品] work_id = {work_id}")

    try:
        data = get_artwork_metadata(work_id)
    except Exception as e:
        print(f"  [错误] 无法获取作品信息: {e}")
        return

    if data.get("error", False):
        msg = data.get("message", "unknown")
        print(f"  [错误] {msg}")
        if "not_found" in msg.lower() or "deleted" in msg.lower():
            print("  提示：作品不存在或已被删除")
        return

    body = data.get("body", {})
    if not body:
        print("  [错误] 作品数据为空，可能是未登录导致的权限问题")
        return

    title = body.get("title", "unknown")
    userName = body.get("userName", "unknown")
    page_count = int(body.get("pageCount", 1))
    urls_data = body.get("urls", {})

    x_restrict = int(body.get("xRestrict", 0) or 0)
    is_r18 = x_restrict >= 1
    subfolder = "R18" if is_r18 else ""

    print(f"  标题: {title}")
    print(f"  画师: {userName}")
    print(f"  页数: {page_count}")
    print(f"  类型: {'R-18' if is_r18 else '全年龄'}")

    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
    work_folder = os.path.join(folder, subfolder, f"{safe_title}_{work_id}")

    # 从元数据获取真实图片URL
    if urls_data:
        original_base = urls_data.get("regular") or urls_data.get("original") or ""
        if page_count == 1:
            img_url = original_base
        else:
            img_url = original_base.replace("_p0", "_p%i") if original_base else None
            if not img_url:
                # fallback: 拼URL
                img_url = f"https://i.pximg.net/img-original/img/{work_id}_p%i.jpg"
    else:
        img_url = None

    if page_count == 1:
        img_url = img_url or f"https://i.pximg.net/img-original/img/{work_id}_p0.jpg"
        print(f"\n  开始下载...")
        save_image(img_url, work_folder)
    else:
        print(f"\n  开始下载 {page_count} 张图片...")
        for i in range(page_count):
            if img_url and "%i" in img_url:
                page_url = img_url % i
            else:
                page_url = f"https://i.pximg.net/img-original/img/{work_id}_p{i}.jpg"
            filename = f"p{i:02d}.jpg"
            save_image(page_url, work_folder, filename)
            if i < page_count - 1:
                time.sleep(PAGE_DELAY + random.uniform(-0.3, 0.5))

    print(f"  [完成] {work_folder}")


# ------------------------------------------------------------
# 下载画师作品
# ------------------------------------------------------------
def download_artist(user_id: str, folder: str):
    print(f"\n[画师] user_id = {user_id}")

    api_url = f"https://www.pixiv.net/ajax/user/{user_id}/profile/all"
    try:
        resp = requests_retry("get", api_url, retries=MAX_RETRIES)
        resp.raise_for_status()
        profile = resp.json()
    except Exception as e:
        print(f"  [错误] {e}")
        return

    if profile.get("error", False):
        print(f"  [错误] {profile.get('message', 'unknown')}")
        return

    body = profile.get("body", {})
    username = body.get("name", user_id)
    illusts = body.get("illusts", {})

    # 获取画师头像 URL
    avatar_url = (
        body.get("extraData", {}).get("preference", {}).get("image")
        or body.get("imageBig")
        or body.get("image")
        or ""
    )

    if not illusts:
        print("  该画师无公开作品")
        return

    print(f"  画师: {username}")
    print(f"  作品数: {len(illusts)}")
    if avatar_url:
        print(f"  头像: {avatar_url}")

    safe_username = re.sub(r'[\\/:*?"<>|]', "_", username)[:30] or f"user_{user_id}"
    artist_folder = os.path.join(folder, safe_username)
    Path(artist_folder).mkdir(parents=True, exist_ok=True)

    # 下载画师头像（已存在则跳过）
    if avatar_url:
        avatar_path = os.path.join(artist_folder, "avatar.jpg")
        if not os.path.exists(avatar_path):
            print(f"\n  下载画师头像...")
            save_image(avatar_url, artist_folder, "avatar.jpg")
        else:
            print(f"\n  [跳过] 头像已存在")

    print(f"\n  开始增量下载（已存在则跳过）...")
    success, skipped, failed = 0, 0, 0

    illust_ids = sorted(illusts.keys(), key=lambda x: int(x))
    for idx, wid in enumerate(illust_ids):
        item = illusts[wid]
        title_hint = item.get("title", "?") if isinstance(item, dict) else "?"
        page_count_hint = int(item.get("pageCount", 1)) if isinstance(item, dict) else 1

        # 获取真实元数据（包含真实标题）
        try:
            meta = get_artwork_metadata(wid)
        except Exception as e:
            print(f"  [{wid}] 元数据获取失败: {e}")
            failed += page_count_hint
            time.sleep(REQUEST_DELAY + random.uniform(0, 1))
            continue

        if meta.get("error", False) or not meta.get("body"):
            print(f"  [{wid}] 无法获取元数据，跳过")
            failed += page_count_hint
            time.sleep(REQUEST_DELAY)
            continue

        meta_body = meta["body"]
        urls_data = meta_body.get("urls", {})
        actual_title = meta_body.get("title", title_hint)
        actual_page_count = int(meta_body.get("pageCount", page_count_hint))

        safe_title = re.sub(r'[\\/:*?"<>|]', "_", actual_title)[:50] or "untitled"

        # 检测 R18：x_restrict = 1 (R-18), 2 (R-18G)
        x_restrict = int(meta_body.get("xRestrict", 0) or 0)
        is_r18 = x_restrict >= 1
        subfolder = "R18" if is_r18 else ""
        work_folder = os.path.join(artist_folder, subfolder, f"{safe_title}_{wid}")
        Path(work_folder).mkdir(parents=True, exist_ok=True)

        # 检查是否全部已存在
        all_exist = all(
            os.path.exists(os.path.join(work_folder, f"p{p:02d}.jpg"))
            for p in range(actual_page_count)
        )
        r18_tag = " [R18]" if is_r18 else ""
        if all_exist:
            skipped += actual_page_count
            print(f"  [跳过]{r18_tag} {safe_title}_{wid}  ({actual_page_count}张)")
            continue

        # 取图片URL
        def get_page_url(idx):
            for key in ("original", "regular", "small", "thumb"):
                u = urls_data.get(key, "")
                if u:
                    return u.replace("_p0", f"_p{idx}") if "_p0" in u else u
            return f"https://i.pximg.net/img-original/img/{wid}_p{idx}.jpg"

        downloaded = False
        for p in range(actual_page_count):
            filename = f"p{p:02d}.jpg"
            filepath = os.path.join(work_folder, filename)
            if os.path.exists(filepath):
                skipped += 1
                continue

            page_url = get_page_url(p)
            ok = save_image(page_url, work_folder, filename)
            if ok:
                success += 1
                downloaded = True
            else:
                failed += 1

            if p < actual_page_count - 1:
                time.sleep(PAGE_DELAY + random.uniform(-0.3, 0.5))

        # 每10个显示进度
        if (idx + 1) % 10 == 0:
            print(f"\n  [进度] {idx + 1}/{len(illust_ids)}  新增:{success} 跳过:{skipped} 失败:{failed}")

        # 作品间延迟
        if idx < len(illust_ids) - 1:
            time.sleep(REQUEST_DELAY + random.uniform(0, 1.5))

    print(f"\n  === 完成 ===")
    print(f"  新增: {success}  |  跳过: {skipped}  |  失败: {failed}")
    print(f"  保存: {artist_folder}")


# ------------------------------------------------------------
# 主入口
# ------------------------------------------------------------
def main():
    args = sys.argv[1:]

    if not args:
        print()
        print("=" * 50)
        print("  Pixiv 图片下载器 v3.2")
        print("  （含重试机制 + 真实URL修复）")
        print("=" * 50)
        print()
        print("  1) 下载作品页（如 https://www.pixiv.net/artworks/12345678）")
        print("  2) 下载画师主页所有作品（如 https://www.pixiv.net/users/123456）")
        print("  3) 更新 Cookie  （Cookie 过期后在此更换）")
        print("  0) 退出")
        print()
        choice = input("请选择 [1/2/3/0]: ").strip()
        print()

        if choice == "1":
            url = input("请输入作品页 URL: ").strip()
            if not url:
                print("URL 不能为空。")
                return
        elif choice == "2":
            url = input("请输入画师主页 URL: ").strip()
            if not url:
                print("URL 不能为空。")
                return
        elif choice == "3":
            update_cookie()
            return
        elif choice == "0":
            return
        else:
            print("无效选择。")
            return
        folder = str(SAVE_FOLDER)

    elif args[0] == "--update-cookie":
        update_cookie()
        return
    elif args[0] == "--check":
        load_cookies()
        check_login()
        return
    else:
        url = args[0].strip()
        folder = args[1] if len(args) > 1 else str(SAVE_FOLDER)

    print("=" * 50)
    print("  Pixiv 图片下载器 v3.2")
    print("=" * 50)

    load_cookies()
    check_login()

    result = parse_url(url)
    if not result:
        print("[错误] 无法识别的 URL")
        print("支持: /artworks/ | /users/")
        sys.exit(1)

    kind, item_id = result
    if kind == "novel":
        print("[提示] 小说暂不支持")
        return

    if kind == "artwork":
        download_artwork(item_id, folder)
    else:
        download_artist(item_id, folder)


if __name__ == "__main__":
    main()
