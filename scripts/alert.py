#!/usr/bin/env python3
"""tmux로 돌려놓은 장시간 스크립트가 끝나면 Discord로 알림을 보낸다.

사용법:
    # 완료 문구만 보내기
    python scripts/alert.py --task "sweep.sh" --status ok

    # 로그 파일의 마지막 부분을 같이 보내기
    python scripts/alert.py --task "sweep.sh" --status ok --log logs/20260712_.../summary.tsv

    # 파이프로 터미널 출력을 그대로 흘려보내기
    bash scripts/sweep.sh 2>&1 | tee sweep.log; python scripts/alert.py --task "sweep.sh" --status $?

    # 셸에서 그대로 이어붙이기 (성공/실패 둘 다 알림)
    bash scripts/sweep.sh; python scripts/alert.py --task "sweep.sh" --status $?
"""

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

MAX_DESCRIPTION_CHARS = 3500  # discord embed description 한도(4096)보다 여유있게


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def parse_status(raw):
    """--status 는 'ok'/'fail' 문자열이나 $? 종료 코드(0/그외) 모두 받는다."""
    raw = str(raw).strip().lower()
    if raw in ("0", "ok", "success", "done"):
        return True
    return False


def build_payload(task, ok, message, username, avatar_url):
    title = f"✅ {task} 완료" if ok else f"❌ {task} 실패"
    color = 0x2ECC71 if ok else 0xE74C3C

    embed = {
        "title": title,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": socket.gethostname()},
    }
    if message:
        if len(message) > MAX_DESCRIPTION_CHARS:
            message = "...(생략)...\n" + message[-MAX_DESCRIPTION_CHARS:]
        embed["description"] = f"```\n{message}\n```"

    payload = {"embeds": [embed]}
    if username:
        payload["username"] = username
    if avatar_url:
        payload["avatar_url"] = avatar_url
    return payload


def send(webhook_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            # User-Agent 없으면 Cloudflare가 봇으로 보고 403 1010으로 막는다.
            "User-Agent": "Mozilla/5.0 (compatible; t2i-lab-alert/1.0)",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        sys.exit(f"[alert] discord 전송 실패: {e.code} {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"[alert] discord 전송 실패: {e.reason}")


def main():
    parser = argparse.ArgumentParser(description="완료 알림을 Discord로 전송")
    parser.add_argument("--task", required=True, help="어떤 작업인지 (예: sweep.sh)")
    parser.add_argument(
        "--status", default="ok", help="'ok'/'fail' 또는 $? 종료 코드 (기본: ok)"
    )
    parser.add_argument("--message", help="직접 넣을 메시지 텍스트")
    parser.add_argument("--log", help="이 파일의 마지막 부분을 첨부 (tail)")
    parser.add_argument("--tail-lines", type=int, default=30, help="--log 사용 시 마지막 몇 줄 (기본 30)")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env_file(os.path.join(repo_root, ".env"))

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        sys.exit("[alert] DISCORD_WEBHOOK_URL이 설정되지 않았습니다 (.env 확인)")

    ok = parse_status(args.status)

    message = args.message
    if message is None and args.log:
        with open(args.log, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        message = "".join(lines[-args.tail_lines :]).rstrip()
    if message is None and not sys.stdin.isatty():
        message = sys.stdin.read().rstrip()
        if message:
            lines = message.splitlines()
            message = "\n".join(lines[-args.tail_lines :])

    payload = build_payload(
        args.task,
        ok,
        message,
        os.environ.get("DISCORD_USERNAME") or None,
        os.environ.get("DISCORD_AVATAR_URL") or None,
    )
    send(webhook_url, payload)
    print("[alert] discord 알림 전송 완료")


if __name__ == "__main__":
    main()
