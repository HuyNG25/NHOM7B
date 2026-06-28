# -*- coding: utf-8 -*-
"""
Script kiểm thử đầy đủ tất cả luồng của Notification Service (B7)
So sánh với yêu cầu đề bài FIT4110 - Đề tài 7
"""
import urllib.request
import json
import sys
import io

# Fix encoding trên Windows (PowerShell dùng cp1252)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
TOKEN = "Bearer mock-jwt-token-for-fit4110"
results = []

def call(label, method, path, body=None, extra_headers=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read().decode("utf-8"))
            results.append({"test": label, "status": r.status, "ok": True, "resp": resp})
            return resp
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8")
        try:
            body_json = json.loads(body_text)
        except:
            body_json = body_text
        results.append({"test": label, "status": e.code, "ok": False, "resp": body_json})
        return None

# ============================================================
# T1: Health check cơ bản
# ============================================================
call("T1 - GET /health", "GET", "/health")

# ============================================================
# T2: Health dependencies (kiểm tra kết nối tới B6, Analytics, Gateway)
# ============================================================
call("T2 - GET /health/dependencies", "GET", "/health/dependencies")

# ============================================================
# T3: POST /api/v1/alerts — ĐÚNG payload gợi ý từ ĐỀ BÀI
# input: alert_id, severity, message, target
# output mong đợi: sent=true, channel, status=delivered
# ============================================================
call("T3 - POST /api/v1/alerts (payload đề bài)", "POST", "/api/v1/alerts",
    body={
        "alert_id": "ALT-001",
        "severity": "high",
        "message": "Unknown person detected near main gate",
        "target": "security_team"
    },
    extra_headers={"Authorization": TOKEN})

# ============================================================
# T4: POST /notifications/events — AlertEventPayload đầy đủ từ B6
# ============================================================
call("T4 - POST /notifications/events (từ B6)", "POST", "/notifications/events",
    body={
        "eventId": "EVT-UUID-B6-001",
        "eventType": "core.alert.created",
        "occurredAt": "2026-06-17T05:00:00Z",
        "source": "core-business-b6",
        "data": {
            "alertId": "ALT-B6-002",
            "severity": "HIGH",
            "message": "Fire detected in Lab A101",
            "targetUserId": "SV001",
            "channels": ["telegram", "discord"]
        }
    },
    extra_headers={"Authorization": TOKEN})

# ============================================================
# T5: POST /analytics/export — S2S từ B6, demo độc lập (không cần token)
# 3 log items: GRANTED (no notify), FIRE_ALARM (CRITICAL), DENIED (HIGH)
# ============================================================
call("T5 - POST /analytics/export (demo độc lập)", "POST", "/analytics/export",
    body={
        "from": "2026-06-17T00:00:00Z",
        "to": "2026-06-17T23:59:59Z",
        "data": [
            {
                "log_type": "ACCESS",
                "timestamp": "2026-06-17T08:30:00Z",
                "details": {"uid": "04:A1:B2:C3", "student_id": "SV001", "class_name": "SE1501", "gate_id": "GATE-A", "action": "GRANTED"}
            },
            {
                "log_type": "FIRE_ALARM",
                "timestamp": "2026-06-17T09:15:00Z",
                "details": {"device_id": "esp32-lab-a101", "location": "Lab A101", "temperature": 52.5, "action": "EVACUATION_TRIGGERED"}
            },
            {
                "log_type": "ACCESS",
                "timestamp": "2026-06-17T10:00:00Z",
                "details": {"uid": "04:FF:EE:DD", "student_id": "SV999", "class_name": "SE1502", "gate_id": "GATE-B", "action": "DENIED"}
            }
        ]
    })

# ============================================================
# T6: POST /analytics/export — Giả lập B6 gửi thật (có X-Source-Service)
# ============================================================
call("T6 - POST /analytics/export (giả lập B6 thật)", "POST", "/analytics/export",
    body={
        "from": "2026-06-17T11:00:00Z",
        "to": "2026-06-17T11:59:59Z",
        "data": [
            {
                "log_type": "FIRE_ALARM",
                "timestamp": "2026-06-17T11:00:00Z",
                "details": {"device_id": "esp32-lab-b202", "location": "Lab B202", "temperature": 75.0, "action": "EVACUATION_TRIGGERED"}
            }
        ]
    },
    extra_headers={"X-Source-Service": "core-business-b6"})

# ============================================================
# T7: Deduplication — Gửi event_id trùng (phải bị chặn 409)
# ============================================================
call("T7 - POST /notifications/events (duplicate eventId)", "POST", "/notifications/events",
    body={
        "eventId": "EVT-UUID-B6-001",   # ← trùng với T4
        "eventType": "core.alert.created",
        "occurredAt": "2026-06-17T05:00:00Z",
        "source": "core-business-b6",
        "data": {
            "alertId": "ALT-DUP",
            "severity": "HIGH",
            "message": "Duplicate event test",
            "targetUserId": None
        }
    },
    extra_headers={"Authorization": TOKEN})

# ============================================================
# T8: GET /notifications/logs — Kiểm tra ghi log sau khi gửi
# ============================================================
call("T8 - GET /notifications/logs", "GET", "/notifications/logs?limit=10",
    extra_headers={"Authorization": TOKEN})

# ============================================================
# T9: GET /api/v1/channels — Kiểm tra trạng thái kênh
# ============================================================
call("T9 - GET /api/v1/channels", "GET", "/api/v1/channels")

# ============================================================
# T10: GET /api/v1/alerts/logs — Dashboard logs (no auth)
# ============================================================
call("T10 - GET /api/v1/alerts/logs", "GET", "/api/v1/alerts/logs?limit=5")

# ============================================================
# T11: Error handling — Thiếu field bắt buộc (phải trả 400)
# ============================================================
call("T11 - POST /api/v1/alerts (thiếu field - expect 400)", "POST", "/api/v1/alerts",
    body={"severity": "high"},
    extra_headers={"Authorization": TOKEN})

# ============================================================
# T12: Auth check — Không có Bearer Token (phải trả 401)
# ============================================================
call("T12 - POST /api/v1/alerts (no token - expect 401)", "POST", "/api/v1/alerts",
    body={"alert_id": "X", "severity": "high", "message": "test", "target": "x"})

# ============================================================
# IN BÁO CÁO
# ============================================================
print()
print("=" * 72)
print("  FULL TEST REPORT — Notification Service (B7)")
print("=" * 72)

ok_count = sum(1 for r in results if r["ok"])
print(f"  Passed: {ok_count}/{len(results)}\n")

for r in results:
    icon = "[PASS]" if r["ok"] else "[FAIL]"
    print(f"{icon} [{r['status']}] {r['test']}")
    resp = r["resp"]
    if isinstance(resp, dict):
        short = json.dumps(resp, ensure_ascii=False)
        if len(short) > 250:
            short = short[:250] + "..."
        print(f"    -> {short}")
    else:
        print(f"    -> {str(resp)[:250]}")
    print()

print("=" * 72)
