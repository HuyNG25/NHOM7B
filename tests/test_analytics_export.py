# -*- coding: utf-8 -*-
"""
Test script cho POST /analytics/export (S2S endpoint từ B6 → B7)

Hỗ trợ 2 chế độ:
  - Demo độc lập : Chạy trực tiếp, không cần X-Source-Service
  - Giả lập B6   : Truyền header X-Source-Service: core-business-b6

Cách dùng:
  python tests/test_analytics_export.py            # demo độc lập
  python tests/test_analytics_export.py --b6       # giả lập B6 gửi
"""

import urllib.request
import json
import sys

BASE_URL = "http://localhost:8086"

# ============================================================
# Payload chuẩn B6 → B7 (theo contract B6 to B5 Analytics Log Export)
# ============================================================
payload = {
    "from": "2026-06-16T00:00:00Z",
    "to": "2026-06-16T23:59:59Z",
    "data": [
        {
            "log_type": "ACCESS",
            "timestamp": "2026-06-16T08:30:00Z",
            "details": {
                "uid": "04:A1:B2:C3",
                "student_id": "SV001",
                "class_name": "SE1501",
                "gate_id": "GATE-A",
                "action": "GRANTED"          # → chỉ ghi log, không notify
            }
        },
        {
            "log_type": "FIRE_ALARM",
            "timestamp": "2026-06-16T09:15:00Z",
            "details": {
                "device_id": "esp32-lab-a101",
                "location": "Lab A101",
                "temperature": 52.5,
                "action": "EVACUATION_TRIGGERED"   # → CRITICAL, trigger notify
            }
        },
        {
            "log_type": "ACCESS",
            "timestamp": "2026-06-16T10:00:00Z",
            "details": {
                "uid": "04:FF:EE:DD",
                "student_id": "SV999",
                "class_name": "SE1502",
                "gate_id": "GATE-B",
                "action": "DENIED"           # → HIGH, trigger notify
            }
        }
    ]
}

# ============================================================
# Xác định chế độ chạy
# ============================================================
simulate_b6 = "--b6" in sys.argv

headers = {
    "Content-Type": "application/json",
    # KHÔNG cần Authorization — đây là S2S endpoint, không phải user endpoint
}

if simulate_b6:
    # Chế độ: Giả lập B6 gửi thật (có header nhận dạng nguồn)
    headers["X-Source-Service"] = "core-business-b6"
    print("🔗 Chế độ: Giả lập B6 (X-Source-Service: core-business-b6)")
else:
    print("🧪 Chế độ: Demo độc lập (không cần X-Source-Service)")

print(f"📡 Gửi tới: POST {BASE_URL}/analytics/export")
print(f"📦 Số log item: {len(payload['data'])}\n")

# ============================================================
# Gửi request
# ============================================================
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    f"{BASE_URL}/analytics/export",
    data=data,
    method="POST",
    headers=headers
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print("✅ Kết quả:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Tóm tắt nhanh
        print(f"\n📊 Tóm tắt:")
        print(f"  - Nguồn nhận dạng : {result.get('received_from', 'N/A')}")
        print(f"  - Tổng log nhận   : {result.get('total_received', 0)}")
        print(f"  - Notification gửi: {result.get('notifications_triggered', 0)}")
        for item in result.get("results", []):
            icon = "🔔" if item["notification_triggered"] else "📝"
            print(f"  {icon} [{item['log_type']}] {item['timestamp']} → {item['reason']}")

except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"❌ HTTP Error {e.code}: {body}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Lỗi kết nối: {e}")
    print(f"   Hãy đảm bảo server đang chạy tại {BASE_URL}")
    sys.exit(1)
