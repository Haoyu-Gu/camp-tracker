#!/bin/bash
# ============================================================
# 高校招生通知爬虫 - 定时任务安装脚本
# 使用 macOS launchd 实现每 12 小时自动运行
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.user.camp-monitor.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

echo "============================================================"
echo "高校招生通知爬虫 - 定时任务安装"
echo "============================================================"
echo ""

# 检查 plist 文件是否存在
if [ ! -f "${PLIST_SRC}" ]; then
    echo "[错误] 找不到 plist 文件: ${PLIST_SRC}"
    exit 1
fi

# 检查 Python 脚本是否存在
if [ ! -f "${SCRIPT_DIR}/crawler.py" ]; then
    echo "[错误] 找不到爬虫脚本: ${SCRIPT_DIR}/crawler.py"
    exit 1
fi

# 检查 Python 依赖
echo "[1/4] 检查 Python 依赖..."
python3 -c "import requests, bs4" 2>/dev/null || {
    echo "  正在安装缺失的 Python 包..."
    pip3 install requests beautifulsoup4
}
echo "  依赖检查通过。"

# 如果已有旧的定时任务，先卸载
echo ""
echo "[2/4] 检查并卸载旧的定时任务..."
if launchctl list | grep -q "${PLIST_NAME%.plist}" 2>/dev/null; then
    echo "  发现旧任务，正在卸载..."
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
    echo "  旧任务已卸载。"
else
    echo "  未发现旧任务。"
fi

# 创建 LaunchAgents 目录（如果不存在）
mkdir -p "${HOME}/Library/LaunchAgents"

# 复制 plist 文件
echo ""
echo "[3/4] 安装 plist 文件..."
cp "${PLIST_SRC}" "${PLIST_DST}"
echo "  已复制到: ${PLIST_DST}"

# 加载定时任务
echo ""
echo "[4/4] 加载定时任务..."
launchctl load "${PLIST_DST}"
echo "  定时任务已加载。"

echo ""
echo "============================================================"
echo "安装完成!"
echo ""
echo "  定时间隔: 每 12 小时运行一次"
echo "  爬虫脚本: ${SCRIPT_DIR}/crawler.py"
echo "  通知汇总: ${SCRIPT_DIR}/updates.md"
echo "  错误日志: ${SCRIPT_DIR}/error.log"
echo "  运行日志: ${SCRIPT_DIR}/launchd_stdout.log"
echo ""
echo "常用命令:"
echo "  手动运行:   python3 ${SCRIPT_DIR}/crawler.py"
echo "  查看状态:   launchctl list | grep camp-monitor"
echo "  停止任务:   launchctl unload ${PLIST_DST}"
echo "  重新加载:   launchctl load ${PLIST_DST}"
echo "  卸载任务:   launchctl unload ${PLIST_DST} && rm ${PLIST_DST}"
echo "============================================================"
