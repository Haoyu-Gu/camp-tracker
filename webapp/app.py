#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
保研夏令营信息展示 Web 应用
Flask 后端：解析 markdown 数据，提供 JSON API
"""

import os
import re
import json
import subprocess
import sys
from datetime import datetime
from flask import Flask, render_template, jsonify, send_from_directory

app = Flask(__name__)

# ========== 路径配置 ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHOOLS_MD = os.path.join(BASE_DIR, "院校网址汇总.md")
UPDATES_MD = os.path.join(BASE_DIR, "monitor", "updates.md")
CRAWLER_PY = os.path.join(BASE_DIR, "monitor", "crawler.py")
RESUME_PATH = os.path.join(BASE_DIR, "个人资料", "简历.pdf")
STATUS_FILE = os.path.join(BASE_DIR, "webapp", "school_status.json")
DEADLINE_FILE = os.path.join(BASE_DIR, "webapp", "school_deadlines.json")

# 可选的状态列表
AVAILABLE_STATUSES = [
    "未开始", "准备中", "已套磁", "材料准备中", "材料已提交",
    "已入营", "已获offer", "已放弃", "待定"
]

# 学校文件夹映射 (id -> 文件夹名)
SCHOOL_FOLDERS = {
    "sjtu_ai": "上交AI",
    "sjtu_cs": "上交计算机",
    "cas_auto": "中科院自动化所",
    "cas_ict": "中科院计算所",
    "pku_ai": "北大智能",
    "pku_cs": "北大计算机",
    "pku_ss": "北大软微",
    "nju_is": "南大智科",
    "nju_cs": "南大计算机",
    "zju_cs": "浙大计算机",
    "thu_ee": "清华电子",
    "thu_auto": "清华自动化",
    "thu_cs": "清华计算机",
    "thu_sz": "清华深圳",
    "fudan": "复旦",
    "ruc_ai": "人大高瓴",
}

# 学校信息 (id -> 完整信息)
SCHOOL_INFO = {
    "sjtu_ai": {"university": "上海交通大学", "department": "人工智能学院", "short": "上交AI"},
    "sjtu_cs": {"university": "上海交通大学", "department": "计算机学院", "short": "上交计算机"},
    "cas_auto": {"university": "中国科学院", "department": "自动化研究所", "short": "中科院自动化所"},
    "cas_ict": {"university": "中国科学院", "department": "计算技术研究所", "short": "中科院计算所"},
    "pku_ai": {"university": "北京大学", "department": "智能学院", "short": "北大智能"},
    "pku_cs": {"university": "北京大学", "department": "计算机学院", "short": "北大计算机"},
    "pku_ss": {"university": "北京大学", "department": "软件与微电子学院", "short": "北大软微"},
    "nju_is": {"university": "南京大学", "department": "智能科学与技术学院", "short": "南大智科"},
    "nju_cs": {"university": "南京大学", "department": "计算机学院", "short": "南大计算机"},
    "zju_cs": {"university": "浙江大学", "department": "计算机科学与技术学院", "short": "浙大计算机"},
    "thu_ee": {"university": "清华大学", "department": "电子工程系", "short": "清华电子"},
    "thu_auto": {"university": "清华大学", "department": "自动化系", "short": "清华自动化"},
    "thu_cs": {"university": "清华大学", "department": "计算机科学与技术系", "short": "清华计算机"},
    "thu_sz": {"university": "清华大学", "department": "深圳国际研究生院", "short": "清华深圳"},
    "fudan": {"university": "复旦大学", "department": "计算机学院", "short": "复旦"},
    "ruc_ai": {"university": "中国人民大学", "department": "高瓴人工智能学院", "short": "人大高瓴"},
}

# 学校到 id 的模糊映射 (updates.md 中的名称 -> school_id)
# 排除关键词（与 crawler.py 保持一致，用于过滤已抓取的历史通知）
EXCLUDE_KEYWORDS = [
    "港澳台", "港澳", "台湾地区", "留学生", "国际学生", "来华留学",
    "网报公告", "网上确认", "初试科目", "考场安排", "条形码", "考点公告",
    "准考证", "复试分数线", "调剂",
    "医学院", "护理", "口腔", "药学", "公共卫生",
    "体育系", "体育学", "法学院", "法律硕士", "法律学",
    "农业与生物", "设计学院", "物流工程", "能源学院",
    "MBA", "EMBA", "MPA", "MEM", "MTT",
    "宣传手册", "宣传册", "招生手册",
]

SCHOOL_NAME_MAP = {
    "上海交通大学 - AI学院": "sjtu_ai",
    "上海交通大学 - 计算机学院": "sjtu_cs",
    "上海交通大学 - 研究生招生网": "__sjtu_dispatch__",  # 按标题内容分配
    "中科院 - 自动化所通知": "cas_auto",
    "中科院 - 自动化所硕士招生": "cas_auto",
    "中科院 - 计算所通知": "cas_ict",
    "中科院 - 计算所招生": "cas_ict",
    "北京大学 - 智能学院": "pku_ai",
    "北京大学 - 计算机学院": "pku_cs",
    "北京大学 - 软微学院": "pku_ss",
    "北京大学 - 夏令营统一页": "__pku_dispatch__",  # 按标题内容分配
    "南京大学 - 智科院": "nju_is",
    "南京大学 - 计算机学院夏令营": "nju_cs",
    "浙江大学 - 计算机学院通知": "zju_cs",
    "浙江大学 - 计算机学院招生": "zju_cs",
    "清华大学 - 电子系动态": "thu_ee",
    "清华大学 - 自动化系通知": "thu_auto",
    "清华大学 - 自动化系研招": "thu_auto",
    "清华大学 - 计算机系通知": "thu_cs",
    "清华大学 - 计算机系招生": "thu_cs",
    "清华大学 - 夏令营统一页": "__thu_dispatch__",  # 按标题内容分配
}


# ========== 数据解析 ==========

def parse_schools_md():
    """解析院校网址汇总.md，提取每个学校的链接"""
    if not os.path.exists(SCHOOLS_MD):
        return {}

    with open(SCHOOLS_MD, "r", encoding="utf-8") as f:
        content = f.read()

    schools = {}
    # 按 ## 数字. 学校名 分割
    sections = re.split(r'\n## \d+\.\s+', content)

    for section in sections[1:]:  # 跳过第一段（标题部分）
        lines = section.strip().split("\n")
        school_name = lines[0].strip()

        links = []
        for line in lines[1:]:
            # 匹配 - **标签**: URL 或 - **标签**: [文本](URL) 格式
            m = re.match(r'-\s+\*\*(.+?)\*\*:\s*(https?://\S+)', line)
            if m:
                links.append({"label": m.group(1), "url": m.group(2)})
            else:
                # 匹配  - 另一入口: URL 格式
                m2 = re.match(r'\s+-\s+(.+?):\s*(https?://\S+)', line)
                if m2:
                    links.append({"label": m2.group(1).strip(), "url": m2.group(2)})

        # 精确映射表（优先级最高）
        name_to_id = {
            "上海交通大学 人工智能学院": "sjtu_ai",
            "上海交通大学 计算机科学与工程系（现计算机学院）": "sjtu_cs",
            "中国科学院 自动化研究所": "cas_auto",
            "中国科学院 计算技术研究所": "cas_ict",
            "北京大学 智能学院": "pku_ai",
            "北京大学 计算机学院": "pku_cs",
            "北京大学 软件与微电子学院": "pku_ss",
            "南京大学 智能科学与技术学院": "nju_is",
            "南京大学 计算机科学与技术系（现计算机学院）": "nju_cs",
            "浙江大学 计算机科学与技术学院": "zju_cs",
            "清华大学 电子工程系": "thu_ee",
            "清华大学 自动化系": "thu_auto",
            "清华大学 计算机科学与技术系": "thu_cs",
        }
        school_id = name_to_id.get(school_name)

        if school_id:
            schools[school_id] = links

    return schools


def _extract_date_from_url(url):
    """从 URL 中提取日期，支持多种高校 URL 格式"""
    # 中科院格式: /202510/t20251016_xxx.html → 2025-10-16
    m = re.search(r'/(\d{4})(\d{2})/t(\d{4})(\d{2})(\d{2})_', url)
    if m:
        return f"{m.group(3)}-{m.group(4)}-{m.group(5)}"
    # 部分高校: /2026/0209/ → 2026-02-09
    m = re.search(r'/(\d{4})/(\d{2})(\d{2})/', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 中科院 PDF: /202602/P020260205xxx.pdf → 2026-02-05
    m = re.search(r'/(\d{4})(\d{2})/P\d{3}(\d{4})(\d{2})(\d{2})', url)
    if m:
        return f"{m.group(3)}-{m.group(4)}-{m.group(5)}"
    # 南大格式: /xx/xx/c57656aXXXXXX/page.htm — 无日期但可从标题年份推断
    # 清华电子/自动化等: /info/1078/4801.htm — 无直接日期
    # 清华/南大/浙大等: /2025/0528/cXXaXXX/page.htm
    m = re.search(r'/(\d{4})/(\d{2})(\d{2})/c\d+a\d+/', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 南大 yzb 格式: /e4/af/c47868a713903/page.htm — 无日期
    # 中科院月份目录: /202510/ (无日)
    m = re.search(r'/(\d{4})(\d{2})/c\d+a\d+/', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    # 通用: URL 路径中的 YYYYMMDD
    m = re.search(r'/(\d{4})(\d{2})(\d{2})/', url)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2015 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def _extract_date_from_title(title):
    """从标题文本中提取日期"""
    chinese_months = {
        '一月': '01', '二月': '02', '三月': '03', '四月': '04',
        '五月': '05', '六月': '06', '七月': '07', '八月': '08',
        '九月': '09', '十月': '10', '十一月': '11', '十二月': '12',
    }

    patterns = [
        # 2025-06-13
        (r'(\d{4})-(\d{2})-(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # 202602/09
        (r'^(\d{4})(\d{2})/(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # 清华自动化格式: "302025-05" → 2025-05-30
        (r'^(\d{2})(\d{4})-(\d{2})', lambda m: f"{m.group(2)}-{m.group(3)}-{m.group(1)}"),
        # 2025.12.25
        (r'(\d{4})\.(\d{2})\.(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # DD2025.MM (如 "152025.12" → 2025-12-15)
        (r'^(\d{2})(\d{4})\.(\d{2})', lambda m: f"{m.group(2)}-{m.group(3)}-{m.group(1)}"),
        # MM.DD/YYYY
        (r'^(\d{2})\.(\d{2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(1)}-{m.group(2)}"),
        # "Feb 10, 2026" 英文日期
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})',
         lambda m: "{}-{}-{}".format(m.group(3), dict(Jan='01',Feb='02',Mar='03',Apr='04',May='05',Jun='06',Jul='07',Aug='08',Sep='09',Oct='10',Nov='11',Dec='12')[m.group(1)], m.group(2).zfill(2))),
        # "2025年6月13日" or "2025年06月"
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日?', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        (r'(\d{4})年(\d{1,2})月', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-01"),
    ]

    for pattern, formatter in patterns:
        dm = re.search(pattern, title)
        if dm:
            return formatter(dm)

    # 中文月份: "19八月" "06九月"
    dm = re.match(r'(\d{2})([\u4e00-\u9fff]+月)', title)
    if dm and dm.group(2) in chinese_months:
        day = dm.group(1)
        month = chinese_months[dm.group(2)]
        # 从标题中提取年份
        ym = re.search(r'(\d{4})年', title)
        year = ym.group(1) if ym else "2025"
        return f"{year}-{month}-{day}"

    return ""


def _validate_date(date_str):
    """验证日期字符串的合法性，修正未来日期"""
    if not date_str:
        return ""
    try:
        from datetime import date as dt_date
        parts = date_str.split('-')
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if not (2015 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31):
            return ""
        # 如果日期在未来，年份减1（标题里的年份通常是招生年份而非发布年份）
        today = dt_date.today()
        try:
            parsed = dt_date(y, m, d)
        except ValueError:
            return ""
        if parsed > today:
            y -= 1
            try:
                parsed = dt_date(y, m, d)
            except ValueError:
                return ""
            return f"{y:04d}-{m:02d}-{d:02d}"
        return date_str
    except (ValueError, IndexError):
        pass
    return ""


# 过短的导航链接（非真正通知）
NAV_LINK_TITLES = {
    "招生工作", "硕士招生", "博士招生", "招生信息", "留学生招生",
    "招生简章", "硕士生招生", "招生培养", "招生办公室",
    "夏令营报名", "预推免报名", "夏令营公示", "预推免公示",
    "夏令营考生登录", "预推免考生登录", "博士招生公示", "院系招生公示",
    "研究生招生", "人才培养", "中国研究生招生信息网",
    "研究生招生管理信息系统", "招生综合信息平台", "招生信息Admissions",
}


def _dispatch_school_id(dispatch_key, title):
    """对综合来源（研招网、夏令营统一页），根据标题内容分配到具体学院"""
    title_lower = title.lower()

    if dispatch_key == "__sjtu_dispatch__":
        if "计算机" in title:
            return "sjtu_cs"
        if "人工智能" in title or "AI" in title_lower or "SAI" in title:
            return "sjtu_ai"
        # 默认两边都给（归到 sjtu_ai 作为兜底，但也复制到 sjtu_cs）
        return "sjtu_ai"

    if dispatch_key == "__pku_dispatch__":
        if "计算机" in title:
            return "pku_cs"
        if "智能" in title:
            return "pku_ai"
        if "软件" in title or "软微" in title:
            return "pku_ss"
        return "pku_cs"

    if dispatch_key == "__thu_dispatch__":
        if "计算机" in title:
            return "thu_cs"
        if "电子" in title:
            return "thu_ee"
        if "自动化" in title:
            return "thu_auto"
        return "thu_cs"

    return None


def parse_updates_md():
    """解析 monitor/updates.md，提取所有通知"""
    if not os.path.exists(UPDATES_MD):
        return []

    with open(UPDATES_MD, "r", encoding="utf-8") as f:
        content = f.read()

    notices = []
    current_source = None
    current_school_id = None

    for line in content.split("\n"):
        line = line.strip()

        # 匹配 ### 学校 - 部门
        if line.startswith("### "):
            current_source = line[4:].strip()
            current_school_id = SCHOOL_NAME_MAP.get(current_source)

        # 匹配 - [标题](链接)
        m = re.match(r'-\s+\[(.+?)\]\((.+?)\)', line)
        if m and current_source:
            title = m.group(1)
            url = m.group(2)

            # 对综合来源，按标题内容分配到具体学院
            notice_school_id = current_school_id
            if current_school_id and current_school_id.startswith("__"):
                notice_school_id = _dispatch_school_id(current_school_id, title)

            # 过滤不相关通知
            if any(kw in title for kw in EXCLUDE_KEYWORDS):
                continue

            # 过滤导航链接
            if title.strip() in NAV_LINK_TITLES:
                continue

            # 过滤标题过短的泛链接（<=6字且不含年份）
            if len(title.strip()) <= 6 and not re.search(r'\d{4}', title):
                continue

            # 提取日期：先从标题提取，再从 URL 提取，最后从标题年份兜底
            date_str = _extract_date_from_title(title)
            if not date_str:
                date_str = _extract_date_from_url(url)
            if not date_str:
                # 兜底：从标题提取年份，如 "2026年" "2025年" "(2025)" "2026级"
                ym = re.search(r'(202[4-9])(?:年|级|\)）)', title)
                if not ym:
                    ym = re.search(r'\(?(202[4-9])\)?', title)
                if ym:
                    date_str = f"{ym.group(1)}-01-01"
            date_str = _validate_date(date_str)

            # 清理标题
            clean_title = title
            clean_title = re.sub(r'^\d{6}/\d{2}', '', clean_title).strip()
            clean_title = re.sub(r'^\d{2}\d{4}\.\d{2}', '', clean_title).strip()
            clean_title = re.sub(r'^\d{4}\.\d{2}\.\d{2}', '', clean_title).strip()
            clean_title = re.sub(r'^\d{2}\.\d{2}/\d{4}', '', clean_title).strip()
            clean_title = re.sub(r'^\d{2}[\u4e00-\u9fff]+月', '', clean_title).strip()
            clean_title = re.sub(r'^\d{4}-\d{2}-\d{2}', '', clean_title).strip()
            clean_title = re.sub(r'\d{4}-\d{2}-\d{2}$', '', clean_title).strip()

            # 跳过清理后标题为空的
            if not clean_title:
                continue

            notices.append({
                "title": clean_title,
                "url": url,
                "date": date_str,
                "source": current_source,
                "school_id": notice_school_id,
                "category": _categorize_notice(clean_title),
            })

    return notices


def _make_file_entry(full, fn, folder_path):
    """构造单个文件条目"""
    rel = os.path.relpath(full, folder_path)
    size = os.path.getsize(full)
    mtime = os.path.getmtime(full)
    return {
        "name": fn,
        "path": rel,
        "full_path": full,
        "size": size,
        "size_str": format_size(size),
        "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
    }


def get_folder_files(school_id):
    """获取学校文件夹下的学院级文件（不含导师子文件夹）"""
    folder_name = SCHOOL_FOLDERS.get(school_id)
    if not folder_name:
        return []

    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return []

    prof_dirs = set(_get_professor_dir_names(folder_path))
    files = []
    for fn in os.listdir(folder_path):
        if fn.startswith('.') or fn == '公示名单' or fn in prof_dirs:
            continue
        full = os.path.join(folder_path, fn)
        if os.path.isfile(full):
            files.append(_make_file_entry(full, fn, folder_path))
        elif os.path.isdir(full):
            # 非导师的子文件夹，递归扫描
            for root, dirs, filenames in os.walk(full):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in filenames:
                    if not f.startswith('.'):
                        fp = os.path.join(root, f)
                        files.append(_make_file_entry(fp, f, folder_path))
    return files


def _get_professor_dir_names(folder_path):
    """返回文件夹下属于导师的子目录名列表（包含陶瓷邮件或套词相关文件的子目录）"""
    prof_dirs = []
    for name in os.listdir(folder_path):
        if name.startswith('.') or name == '公示名单':
            continue
        sub = os.path.join(folder_path, name)
        if not os.path.isdir(sub):
            continue
        # 检查子目录内是否有陶瓷/套词/回复相关文件
        for fn in os.listdir(sub):
            fn_lower = fn.lower()
            if any(kw in fn_lower for kw in ["陶瓷", "套词", "套磁", "reply", "回复"]):
                prof_dirs.append(name)
                break
    return prof_dirs


def get_professors(school_id):
    """获取学校下的导师列表及其文件"""
    folder_name = SCHOOL_FOLDERS.get(school_id)
    if not folder_name:
        return []

    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return []

    prof_dirs = _get_professor_dir_names(folder_path)
    professors = []
    for prof_name in sorted(prof_dirs):
        prof_path = os.path.join(folder_path, prof_name)
        prof_files = []
        for fn in os.listdir(prof_path):
            if fn.startswith('.'):
                continue
            full = os.path.join(prof_path, fn)
            if os.path.isfile(full):
                prof_files.append(_make_file_entry(full, fn, folder_path))

        # 判断套磁状态
        file_names_lower = [f["name"].lower() for f in prof_files]
        has_reply = any("reply" in f or "回复" in f for f in file_names_lower)
        has_draft = any("陶瓷" in f or "套词" in f or "套磁" in f for f in file_names_lower)
        if has_reply:
            status = "已回复"
        elif has_draft:
            status = "待发送"
        else:
            status = "未开始"

        professors.append({
            "name": prof_name,
            "status": status,
            "files": prof_files,
            "file_count": len(prof_files),
        })
    return professors


def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def load_manual_status():
    """加载手动设置的状态"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_manual_status(data):
    """保存手动设置的状态"""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_deadlines():
    """加载截止日期"""
    if os.path.exists(DEADLINE_FILE):
        try:
            with open(DEADLINE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_deadlines(data):
    """保存截止日期"""
    with open(DEADLINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _categorize_notice(title):
    """根据标题对通知进行分类"""
    if any(kw in title for kw in ["夏令营", "暑期学校", "暑期项目", "开放日", "优才计划", "春季营", "冬令营"]):
        return "夏令营"
    if any(kw in title for kw in ["公示", "拟录取", "入营名单", "营员", "录取名单"]):
        return "录取公示"
    if any(kw in title for kw in ["预推免", "推免", "推荐免试", "接收推免"]):
        return "预推免"
    if any(kw in title for kw in ["招生简章", "招生办法", "招生说明", "招收", "考核及录取"]):
        return "招生简章"
    if any(kw in title for kw in ["直博", "硕博连读", "博士研究生招生", "申请-考核"]):
        return "博士招生"
    return "其他"


def determine_status(school_id):
    """根据手动设置或文件夹内容判断申请状态（手动优先）"""
    manual = load_manual_status()
    if school_id in manual:
        return manual[school_id]

    folder_name = SCHOOL_FOLDERS.get(school_id)
    if not folder_name:
        return "未开始"

    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return "未开始"

    all_files = []
    for root, dirs, filenames in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '公示名单']
        for fn in filenames:
            if not fn.startswith('.'):
                all_files.append(fn.lower())

    if not all_files:
        return "未开始"

    # 判断逻辑
    # 陶瓷邮件草稿不算已套磁，只有回复/已发送才算
    has_reply = any("reply" in f or "回复" in f for f in all_files)
    has_draft = any("陶瓷邮件" in f or "陶瓷" in f for f in all_files)
    has_sent = any(("套词" in f or "套磁" in f or "邮件" in f) and "陶瓷" not in f for f in all_files)
    has_material = any("申请" in f or "材料" in f or "计划书" in f or "简历" in f or "成绩" in f or "证明" in f for f in all_files)
    has_submitted = any("提交" in f or "确认" in f or "报名" in f for f in all_files)
    if has_submitted:
        return "材料已提交"
    elif has_material:
        return "材料准备中"
    elif has_reply:
        return "已套磁"
    elif has_sent:
        return "已套磁"
    elif has_draft:
        return "待套磁"
    else:
        return "未开始"


# ========== API 路由 ==========

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/profile")
def api_profile():
    """返回用户基本信息"""
    # TODO: 修改为你的个人信息
    return jsonify({
        "name": "你的名字",
        "university": "你的大学",
        "major": "你的专业",
        "gpa": "X.XX / 4.0",
        "rank": "X / XX",
        "papers": [
            {"title": "论文1", "status": "Accept", "note": ""},
            {"title": "论文2", "status": "Under Review", "note": ""},
        ],
        "resume_available": os.path.exists(RESUME_PATH),
    })


@app.route("/api/schools")
def api_schools():
    """返回所有学校信息（含链接、状态、最新通知）"""
    school_links = parse_schools_md()
    all_notices = parse_updates_md()
    deadlines = load_deadlines()

    result = []
    for sid, info in SCHOOL_INFO.items():
        # 该校通知
        school_notices = [n for n in all_notices if n.get("school_id") == sid]
        # 按日期排序（有日期的排前面，日期最新的排最前）
        dated = [n for n in school_notices if n.get("date")]
        undated = [n for n in school_notices if not n.get("date")]
        dated.sort(key=lambda x: x["date"], reverse=True)
        school_notices = dated + undated

        latest_notice = None
        if school_notices:
            # 优先取有日期的通知
            best = dated[0] if dated else school_notices[0]
            latest_notice = {
                "title": best["title"][:60],
                "date": best.get("date", ""),
                "url": best["url"],
            }

        links = school_links.get(sid, [])
        official_url = links[0]["url"] if links else ""
        admission_url = ""
        for lk in links:
            if "招生" in lk["label"]:
                admission_url = lk["url"]
                break

        status = determine_status(sid)
        files = get_folder_files(sid)
        notice_count = len(school_notices)

        profs = get_professors(sid)

        result.append({
            "id": sid,
            "university": info["university"],
            "department": info["department"],
            "short": info["short"],
            "status": status,
            "deadline": deadlines.get(sid, ""),
            "official_url": official_url,
            "admission_url": admission_url,
            "links": links,
            "latest_notice": latest_notice,
            "notice_count": notice_count,
            "file_count": len(files),
            "professor_count": len(profs),
        })

    return jsonify(result)


@app.route("/api/notices")
def api_notices():
    """返回所有通知"""
    notices = parse_updates_md()
    return jsonify(notices)


@app.route("/api/statuses")
def api_statuses():
    """返回可用的状态列表"""
    return jsonify(AVAILABLE_STATUSES)


@app.route("/api/school/<school_id>/status", methods=["PUT"])
def api_update_status(school_id):
    """手动更新学校状态"""
    if school_id not in SCHOOL_INFO:
        return jsonify({"error": "未找到该学校"}), 404

    from flask import request
    data = request.get_json()
    new_status = data.get("status", "").strip()

    if not new_status:
        return jsonify({"error": "状态不能为空"}), 400

    manual = load_manual_status()
    if new_status == "__auto__":
        # 特殊值：删除手动状态，恢复自动检测
        manual.pop(school_id, None)
    else:
        manual[school_id] = new_status
    save_manual_status(manual)

    return jsonify({"success": True, "status": determine_status(school_id)})


@app.route("/api/school/<school_id>/deadline", methods=["PUT"])
def api_update_deadline(school_id):
    """手动更新学校截止日期"""
    if school_id not in SCHOOL_INFO:
        return jsonify({"error": "未找到该学校"}), 404

    from flask import request
    data = request.get_json()
    deadline = data.get("deadline", "").strip()

    dl = load_deadlines()
    if deadline:
        dl[school_id] = deadline
    else:
        dl.pop(school_id, None)
    save_deadlines(dl)

    return jsonify({"success": True, "deadline": deadline})


@app.route("/api/school/<school_id>")
def api_school_detail(school_id):
    """返回单个学校详情"""
    if school_id not in SCHOOL_INFO:
        return jsonify({"error": "未找到该学校"}), 404

    info = SCHOOL_INFO[school_id]
    school_links = parse_schools_md()
    all_notices = parse_updates_md()

    school_notices = [n for n in all_notices if n.get("school_id") == school_id]
    school_notices.sort(key=lambda x: x.get("date", ""), reverse=True)

    links = school_links.get(school_id, [])
    files = get_folder_files(school_id)
    status = determine_status(school_id)

    profs = get_professors(school_id)

    return jsonify({
        "id": school_id,
        "university": info["university"],
        "department": info["department"],
        "short": info["short"],
        "status": status,
        "links": links,
        "notices": school_notices,
        "files": files,
        "professors": profs,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """触发爬虫运行"""
    if not os.path.exists(CRAWLER_PY):
        return jsonify({"success": False, "message": "爬虫脚本不存在"}), 500

    try:
        result = subprocess.run(
            [sys.executable, CRAWLER_PY],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(CRAWLER_PY),
        )
        output = result.stdout + result.stderr
        return jsonify({
            "success": result.returncode == 0,
            "message": "爬虫运行完成" if result.returncode == 0 else "爬虫运行出错",
            "output": output[-2000:] if len(output) > 2000 else output,  # 限制输出长度
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "爬虫运行超时（120秒）"}), 504
    except Exception as e:
        return jsonify({"success": False, "message": f"运行失败: {str(e)}"}), 500


@app.route("/api/resume")
def api_resume():
    """提供简历 PDF 下载"""
    if os.path.exists(RESUME_PATH):
        directory = os.path.dirname(RESUME_PATH)
        filename = os.path.basename(RESUME_PATH)
        return send_from_directory(directory, filename, mimetype="application/pdf")
    return jsonify({"error": "简历文件不存在"}), 404


@app.route("/api/file/<school_id>/<path:filepath>")
def api_file(school_id, filepath):
    """提供学校文件夹下文件的访问"""
    folder_name = SCHOOL_FOLDERS.get(school_id)
    if not folder_name:
        return jsonify({"error": "未找到该学校"}), 404

    folder_path = os.path.join(BASE_DIR, folder_name)
    full_path = os.path.normpath(os.path.join(folder_path, filepath))

    # 安全检查：防止路径穿越
    if not full_path.startswith(folder_path):
        return jsonify({"error": "非法路径"}), 403

    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))

    return jsonify({"error": "文件不存在"}), 404


if __name__ == "__main__":
    print("=" * 50)
    print("  保研夏令营信息展示系统")
    print("  访问地址: http://localhost:5208")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5208, debug=False)
