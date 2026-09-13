# -*- coding: utf-8 -*-
"""天翼云容器飞书通知模块。

用法：
    from feishu_notify import send_feishu_text, record_result

    # 实时通知 + 记录结果
    record_result("AI对话", True, "对话任务执行完成，AI已回复")
    send_feishu_text("✅ AI对话 成功")

    # 命令行汇总（cron 22:00 调用）
    python3 feishu_notify.py --summary
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    import urllib.request as _ur
    requests = None

FEISHU_WEBHOOK = os.getenv(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/7ef66b64-389b-47dd-8251-ab03ed7c1dbc",
)
RESULT_FILE = "/app/data/task_results.json"

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def send_feishu_text(webhook_url, content, msg_type="text"):
    """发送飞书群机器人消息。返回 True/False。"""
    headers = {"Content-Type": "application/json"}
    data = {"msg_type": msg_type, "content": {"text": content}}
    try:
        if requests is not None:
            resp = requests.post(webhook_url, headers=headers, data=json.dumps(data), timeout=15)
            resp.raise_for_status()
            result = resp.json()
        else:
            body = json.dumps(data).encode("utf-8")
            req = _ur.Request(webhook_url, data=body, headers=headers, method="POST")
            with _ur.urlopen(req, timeout=15) as r:
                result = json.loads(r.read().decode("utf-8", errors="replace"))
        if result.get("code", -1) == 0:
            return True
        else:
            print(f"[notify] 飞书发送失败: {result}")
            return False
    except Exception as e:
        print(f"[notify] 飞书发送异常: {e}")
        return False


def _load_results():
    if not os.path.exists(RESULT_FILE):
        return {}
    try:
        with open(RESULT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_results(results):
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def record_result(task_name, success, summary, webhook_url=None):
    """记录一次任务结果到 JSON，并实时推送飞书。

    task_name: 任务名（如 AI对话 / 云电脑保活）
    success:   True/False
    summary:   摘要文本
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    today = now[:10]
    results = _load_results()
    day = results.setdefault(today, [])
    day.append({"time": now, "task": task_name, "success": success, "summary": summary})
    _save_results(results)

    icon = "✅" if success else "❌"
    text = f"{icon}【{task_name}】{now}\n{summary}"
    if webhook_url is None:
        webhook_url = FEISHU_WEBHOOK
    send_feishu_text(webhook_url, text)
    return True


def send_daily_summary(webhook_url=None):
    """读取当天任务结果，生成一条汇总推送，然后清理当天记录。"""
    today = time.strftime("%Y-%m-%d")
    results = _load_results()
    day = results.get(today, [])

    if webhook_url is None:
        webhook_url = FEISHU_WEBHOOK

    if not day:
        text = f"📋【天翼云任务汇总 {today}】\n今日暂无任务执行记录。"
        send_feishu_text(webhook_url, text)
        return

    # 汇总
    total = len(day)
    ok = sum(1 for r in day if r.get("success"))
    fail = total - ok

    lines = [f"📋【天翼云任务汇总 {today}】", f"总计 {total} 次 | ✅成功 {ok} | ❌失败 {fail}", ""]
    for r in day:
        icon = "✅" if r.get("success") else "❌"
        lines.append(f"{icon} {r.get('task')} {r.get('time','')[:5]}")
        if r.get("summary"):
            lines.append(f"   {r['summary']}")
    lines.append("")
    lines.append("—— 自动生成，无需回复 ——")

    send_feishu_text(webhook_url, "\n".join(lines))

    # 清理当天记录（只留近 7 天历史）
    for d in list(results.keys()):
        if d < today and (today[:4] == d[:4]):
            # 保留当天即可，历史直接清
            pass
    results[today] = []
    _save_results(results)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summary":
        send_daily_summary()
        print("[notify] 每日汇总已发送")
    else:
        print("[notify] 用法: feishu_notify.py --summary")
