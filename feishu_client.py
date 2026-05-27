import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

import httpx


def sign_feishu_webhook(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send_feishu_message(webhook_url: str, content: str, secret: Optional[str] = None) -> dict:
    timestamp = str(int(time.time()))
    payload = {
        "msg_type": "text",
        "content": {"text": content},
    }
    if secret:
        payload["timestamp"] = timestamp
        payload["sign"] = sign_feishu_webhook(secret, timestamp)

    headers = {"Content-Type": "application/json"}
    resp = httpx.post(webhook_url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def send_alert(content: str, dry_run: bool = False) -> Optional[dict]:
    webhook_url = os.environ.get("FEISHU_WEBHOOK", "")
    secret = os.environ.get("FEISHU_SECRET", "")

    if not webhook_url:
        if dry_run:
            print("[DRY-RUN] No FEISHU_WEBHOOK configured. Would send:")
            print(content)
            return None
        raise ValueError("FEISHU_WEBHOOK environment variable is required")

    if dry_run:
        print("[DRY-RUN] Would send to Feishu:")
        print(content)
        return None

    return send_feishu_message(webhook_url, content, secret if secret else None)
