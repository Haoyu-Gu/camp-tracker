#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高校招生通知爬虫
定时抓取多个高校/研究所的招生通知页面，筛选夏令营、预推免、招生相关通知。
"""

import os
import sys
import json
import hashlib
import time
import random
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("requests 未安装，正在安装...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("beautifulsoup4 未安装，正在安装...")
    os.system(f"{sys.executable} -m pip install beautifulsoup4")
    from bs4 import BeautifulSoup

# ========== 配置 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_items.json")
UPDATES_FILE = os.path.join(BASE_DIR, "updates.md")
ERROR_LOG = os.path.join(BASE_DIR, "error.log")

# 匹配关键词（必须命中至少一个）
KEYWORDS = [
    "夏令营", "预推免", "推免", "招生", "暑期学校",
    "开放日", "优才", "直博", "招收", "遴选", "保研",
    "公示", "拟录取", "入营", "名单", "营员",
]

# 排除关键词（命中任一则过滤掉）
EXCLUDE_KEYWORDS = [
    # 不适用的招生类型
    "港澳台", "港澳", "台湾地区", "留学生", "国际学生", "来华留学",
    # 统考相关（用户走推免，不走考研）
    "网报公告", "网上确认", "初试科目", "考场安排", "条形码", "考点公告",
    "准考证", "复试分数线", "调剂",
    # 不相关的学院/专业
    "医学院", "护理", "口腔", "药学", "公共卫生",
    "体育系", "体育学", "法学院", "法律硕士", "法律学",
    "农业与生物", "设计学院", "物流工程", "能源学院",
    "MBA", "EMBA", "MPA", "MEM", "MTT",
    # 宣传册类（非通知）
    "宣传手册", "宣传册", "招生手册",
]

# User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 10  # 秒

# 请求间隔（秒）
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# 需要监控的 URL 列表
MONITOR_TARGETS = [
    # 上海交通大学
    {
        "school": "上海交通大学",
        "department": "AI学院",
        "url": "https://sai.sjtu.edu.cn/cn/list/qs",
    },
    {
        "school": "上海交通大学",
        "department": "计算机学院",
        "url": "https://www.cs.sjtu.edu.cn/bsyjs_zsgz.html",
    },
    {
        "school": "上海交通大学",
        "department": "研究生招生网",
        "url": "https://yzb.sjtu.edu.cn/",
    },
    # 中科院
    {
        "school": "中科院",
        "department": "自动化所通知",
        "url": "http://www.ia.cas.cn/qtgn/tzgg/",
    },
    {
        "school": "中科院",
        "department": "自动化所硕士招生",
        "url": "https://ia.cas.cn/yjsjy/zs/sszs/",
    },
    {
        "school": "中科院",
        "department": "计算所通知",
        "url": "http://www.ict.ac.cn/xwgg/tzgg/",
    },
    {
        "school": "中科院",
        "department": "计算所招生",
        "url": "https://ict.cas.cn/yjsjy/zsxx/",
    },
    # 北京大学
    {
        "school": "北京大学",
        "department": "智能学院",
        "url": "https://sai.pku.edu.cn/rcpy/yjszs.htm",
    },
    {
        "school": "北京大学",
        "department": "计算机学院",
        "url": "https://cs.pku.edu.cn/zsxx/yjszs.htm",
    },
    {
        "school": "北京大学",
        "department": "软微学院",
        "url": "https://ss.pku.edu.cn/zsxx/zstz/index.htm",
    },
    {
        "school": "北京大学",
        "department": "夏令营统一页",
        "url": "https://admission.pku.edu.cn/xly/index.htm",
    },
    # 南京大学
    {
        "school": "南京大学",
        "department": "智科院",
        "url": "https://is.nju.edu.cn/yjszs/list.htm",
    },
    {
        "school": "南京大学",
        "department": "计算机学院夏令营",
        "url": "https://yzb.nju.edu.cn/xlyxx/main.htm",
    },
    # 浙江大学
    {
        "school": "浙江大学",
        "department": "计算机学院通知",
        "url": "http://www.cs.zju.edu.cn/csen/26994/list.htm",
    },
    {
        "school": "浙江大学",
        "department": "计算机学院招生",
        "url": "http://www.cs.zju.edu.cn/csen/26697/list.htm",
    },
    # 清华大学
    {
        "school": "清华大学",
        "department": "电子系动态",
        "url": "https://www.ee.tsinghua.edu.cn/dzxw/dtxx.htm",
    },
    {
        "school": "清华大学",
        "department": "自动化系通知",
        "url": "http://www.au.tsinghua.edu.cn/tzgg.htm",
    },
    {
        "school": "清华大学",
        "department": "自动化系研招",
        "url": "https://www.au.tsinghua.edu.cn/zsjy/yjszs.htm",
    },
    {
        "school": "清华大学",
        "department": "计算机系通知",
        "url": "https://www.cs.tsinghua.edu.cn/index/tzgg.htm",
    },
    {
        "school": "清华大学",
        "department": "计算机系招生",
        "url": "https://www.cs.tsinghua.edu.cn/zszp/zsxx.htm",
    },
    {
        "school": "清华大学",
        "department": "夏令营统一页",
        "url": "https://yz.tsinghua.edu.cn/xlyxx.htm",
    },
]


# ========== 工具函数 ==========

def setup_logging():
    """配置日志记录"""
    logging.basicConfig(
        filename=ERROR_LOG,
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
    )


def load_seen_items():
    """加载已见条目"""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logging.warning("seen_items.json 读取失败，将使用空记录")
    return {}


def save_seen_items(seen):
    """保存已见条目"""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def make_item_id(title, url):
    """为条目生成唯一 ID（基于标题和链接的 hash）"""
    raw = f"{title.strip()}|{url.strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def matches_keywords(text):
    """检查文本是否包含任何关键词"""
    if not text:
        return False
    for kw in KEYWORDS:
        if kw in text:
            return True
    return False


def should_exclude(text):
    """检查文本是否命中排除关键词"""
    if not text:
        return False
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return True
    return False


def fetch_page(url):
    """
    抓取页面内容，返回 BeautifulSoup 对象。
    自动尝试多种编码。
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
    resp.raise_for_status()

    # 尝试从响应头或 meta 标签获取正确编码
    # requests 有时猜错中文页面编码
    content_type = resp.headers.get("Content-Type", "")
    if "charset" in content_type.lower():
        # 响应头里有 charset，requests 通常能处理
        pass
    else:
        # 尝试从 HTML meta 中检测
        apparent = resp.apparent_encoding
        if apparent and apparent.lower() not in ("ascii",):
            resp.encoding = apparent
        else:
            resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    # 再次检查 meta charset
    meta_charset = soup.find("meta", attrs={"charset": True})
    if meta_charset:
        declared = meta_charset["charset"]
        if declared.lower() != resp.encoding.lower():
            resp.encoding = declared
            soup = BeautifulSoup(resp.text, "html.parser")
    else:
        meta_content_type = soup.find("meta", attrs={"http-equiv": re.compile("content-type", re.I)})
        if meta_content_type and meta_content_type.get("content"):
            match = re.search(r"charset=([^\s;]+)", meta_content_type["content"], re.I)
            if match:
                declared = match.group(1)
                if declared.lower() != resp.encoding.lower():
                    resp.encoding = declared
                    soup = BeautifulSoup(resp.text, "html.parser")

    return soup


def extract_links(soup, base_url):
    """
    从页面提取所有带文本的链接条目。
    返回列表: [{"title": ..., "url": ...}, ...]
    """
    items = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        title = a_tag.get_text(strip=True)
        href = a_tag["href"].strip()

        # 跳过空标题、过短标题、锚点、javascript
        if not title or len(title) < 4:
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue

        # 转换为绝对 URL
        full_url = urljoin(base_url, href)

        # 去重
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        items.append({
            "title": title,
            "url": full_url,
        })

    return items


def filter_by_keywords(items):
    """按关键词过滤条目（匹配关键词且不命中排除词）"""
    return [
        item for item in items
        if matches_keywords(item["title"]) and not should_exclude(item["title"])
    ]


def append_to_updates(new_items):
    """将新条目追加到 updates.md"""
    if not new_items:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(UPDATES_FILE) and os.path.getsize(UPDATES_FILE) > 0

    with open(UPDATES_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("# 高校招生通知监控\n\n")
            f.write("本文件由爬虫自动生成，记录新发现的招生相关通知。\n\n")
            f.write("---\n\n")

        f.write(f"## {now} 更新（共 {len(new_items)} 条新通知）\n\n")

        # 按学校分组
        grouped = {}
        for item in new_items:
            key = f"{item['school']} - {item['department']}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)

        for source, entries in grouped.items():
            f.write(f"### {source}\n\n")
            for entry in entries:
                f.write(f"- [{entry['title']}]({entry['url']})\n")
            f.write("\n")

        f.write("---\n\n")


# ========== 主逻辑 ==========

def crawl_target(target, seen):
    """
    抓取单个目标页面，返回新发现的条目列表。
    """
    school = target["school"]
    department = target["department"]
    url = target["url"]
    new_items = []

    try:
        soup = fetch_page(url)
        all_links = extract_links(soup, url)
        matched = filter_by_keywords(all_links)

        for item in matched:
            item_id = make_item_id(item["title"], item["url"])
            if item_id not in seen:
                seen[item_id] = {
                    "title": item["title"],
                    "url": item["url"],
                    "school": school,
                    "department": department,
                    "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                item["school"] = school
                item["department"] = department
                new_items.append(item)

    except requests.exceptions.Timeout:
        logging.error(f"[超时] {school} {department}: {url}")
        print(f"  [超时] {school} - {department}: {url}")
    except requests.exceptions.ConnectionError:
        logging.error(f"[连接失败] {school} {department}: {url}")
        print(f"  [连接失败] {school} - {department}: {url}")
    except requests.exceptions.HTTPError as e:
        logging.error(f"[HTTP错误] {school} {department}: {url} -> {e}")
        print(f"  [HTTP错误] {school} - {department}: {url} -> {e}")
    except Exception as e:
        logging.error(f"[未知错误] {school} {department}: {url} -> {type(e).__name__}: {e}")
        print(f"  [错误] {school} - {department}: {url} -> {type(e).__name__}: {e}")

    return new_items


def main():
    # 抑制 InsecureRequestWarning（因为 verify=False）
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    setup_logging()

    print("=" * 60)
    print("高校招生通知爬虫")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"监控目标: {len(MONITOR_TARGETS)} 个页面")
    print("=" * 60)

    seen = load_seen_items()
    all_new_items = []

    for i, target in enumerate(MONITOR_TARGETS):
        label = f"{target['school']} - {target['department']}"
        print(f"\n[{i+1}/{len(MONITOR_TARGETS)}] 正在抓取: {label}")
        print(f"  URL: {target['url']}")

        new_items = crawl_target(target, seen)

        if new_items:
            print(f"  -> 发现 {len(new_items)} 条新通知")
            for item in new_items:
                print(f"     - {item['title']}")
            all_new_items.extend(new_items)
        else:
            print(f"  -> 无新通知")

        # 礼貌等待
        if i < len(MONITOR_TARGETS) - 1:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)

    # 保存已见条目
    save_seen_items(seen)

    # 输出新条目
    if all_new_items:
        append_to_updates(all_new_items)
        print("\n" + "=" * 60)
        print(f"本次共发现 {len(all_new_items)} 条新通知")
        print(f"已追加到: {UPDATES_FILE}")
    else:
        print("\n" + "=" * 60)
        print("本次未发现新通知")

    print(f"已见条目总数: {len(seen)}")
    print("=" * 60)

    return len(all_new_items)


if __name__ == "__main__":
    new_count = main()
    sys.exit(0)
