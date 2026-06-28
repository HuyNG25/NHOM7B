"""
integration.py — Dịch vụ tích hợp với các service khác trong hệ thống Smart Campus.

Xử lý tất cả các cuộc gọi ra ngoài (outbound HTTP calls):
  - Core Business B6: Gửi callback xác nhận sau khi thông báo được dispatch
  - Analytics Service: Đẩy log thông báo để phân tích
  - API Gateway: (Nếu cần xác nhận định tuyến)

Cơ chế:
  - Nếu URL là placeholder hoặc MOCK=true → ghi log giả, không gọi mạng
  - Nếu có URL thật → gọi HTTP với timeout và retry
  - Tự động phát hiện URL chưa cấu hình (chứa <> hoặc rỗng)
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional, Tuple
from src.utils.logger import app_logger


# ============================================================
# Hàm kiểm tra URL hợp lệ hay chưa
# ============================================================
def _is_placeholder(url: str) -> bool:
    """
    Trả về True nếu URL chưa được cấu hình (còn là placeholder).
    Ví dụ: 'http://<IP_B6>:<PORT>' → True
    """
    if not url:
        return True
    if "<" in url or ">" in url:
        return True
    if url in ["http://", "https://", "http://localhost", "http://127.0.0.1"]:
        return True
    return False


def _is_mocked(env_key: str) -> bool:
    """Đọc biến môi trường MOCK_* và trả về True nếu là mock."""
    return os.getenv(env_key, "true").lower() == "true"


# ============================================================
# Core Business B6 — Callback
# ============================================================
def call_b6_callback(
    event_id: str,
    ticket_id: str,
    status: str,
    channels_dispatched: list,
) -> str:
    """
    Gửi callback tới Core Business (B6) báo cáo kết quả xử lý thông báo.

    Returns:
        "mocked"  — khi MOCK_B6_CALLBACK=true hoặc URL chưa cấu hình
        "success" — gọi thật thành công
        "failed"  — gọi thật thất bại
    """
    b6_url = os.getenv("WEBHOOK_URL", "")
    if not b6_url:
        b6_url_base = os.getenv("B6_BASE_URL", "")
        b6_url = f"{b6_url_base.rstrip('/')}/alerts"

    mock_flag = _is_mocked("MOCK_B6_CALLBACK")

    # Tự động mock nếu URL là placeholder
    if mock_flag or _is_placeholder(b6_url):
        app_logger.info(json.dumps({
            "event": "b6_callback_mocked",
            "reason": "MOCK_B6_CALLBACK=true hoặc WEBHOOK_URL/B6_BASE_URL chưa cấu hình",
            "event_id": event_id,
            "ticket_id": ticket_id,
            "status": status,
            "channels": channels_dispatched,
            "note": "Khi có IP thật: đặt WEBHOOK_URL/B6_BASE_URL và MOCK_B6_CALLBACK=false trong .env"
        }))
        return "mocked"
    payload = {
        "eventId": event_id,
        "ticket_id": ticket_id,
        "status": status,
        "channels_dispatched": channels_dispatched,
        "source": "notification-service-b7"
    }

    return _http_post(
        service_name="Core Business B6",
        url=b6_url,
        payload=payload,
        timeout=5,
        retries=2
    )


# ============================================================
# Analytics Service — Push Log
# ============================================================
def push_log_to_analytics(log_entry: Dict[str, Any]) -> str:
    """
    Đẩy log thông báo sang Analytics Service.

    Returns:
        "mocked"  — khi MOCK_ANALYTICS=true hoặc URL chưa cấu hình
        "success" — đẩy thành công
        "failed"  — đẩy thất bại
    """
    analytics_url_base = os.getenv("ANALYTICS_BASE_URL", "")
    mock_flag = _is_mocked("MOCK_ANALYTICS")

    # Tự động mock nếu URL là placeholder
    if mock_flag or _is_placeholder(analytics_url_base):
        app_logger.info(json.dumps({
            "event": "analytics_push_mocked",
            "reason": "MOCK_ANALYTICS=true hoặc ANALYTICS_BASE_URL chưa cấu hình",
            "log_ticket_id": log_entry.get("ticket_id"),
            "note": "Khi có IP thật: đặt ANALYTICS_BASE_URL và MOCK_ANALYTICS=false trong .env"
        }))
        return "mocked"

    analytics_url = f"{analytics_url_base.rstrip('/')}/logs/notifications"
    return _http_post(
        service_name="Analytics Service",
        url=analytics_url,
        payload=log_entry,
        timeout=4,
        retries=1
    )


# ============================================================
# Mobile App (B5) — Push Alert
# ============================================================
def push_alert_to_b5(alert_payload: Dict[str, Any]) -> str:
    """
    Đẩy cảnh báo đã lọc (real-time) sang B5 (Mobile App).

    Returns:
        "mocked"  — khi MOCK_B5=true hoặc URL chưa cấu hình
        "success" — đẩy thành công
        "failed"  — đẩy thất bại
    """
    b5_url_base = os.getenv("B5_BASE_URL", "")
    mock_flag = _is_mocked("MOCK_B5")

    if mock_flag or _is_placeholder(b5_url_base):
        app_logger.info(json.dumps({
            "event": "b5_push_mocked",
            "reason": "MOCK_B5=true hoặc B5_BASE_URL chưa cấu hình",
            "alert_event_id": alert_payload.get("event_id"),
            "note": "Khi có IP thật: đặt B5_BASE_URL và MOCK_B5=false trong .env"
        }))
        return "mocked"

    b5_url = f"{b5_url_base.rstrip('/')}/api/v1/alerts/receive"
    return _http_post(
        service_name="Mobile App B5",
        url=b5_url,
        payload=alert_payload,
        timeout=4,
        retries=1
    )


# ============================================================
# Health Check — Kiểm tra kết nối tới service khác
# ============================================================
def check_service_health(service_name: str, base_url: str, health_path: str = "/health") -> Dict[str, Any]:
    """
    Kiểm tra xem một service khác có đang chạy và kết nối được không.
    Dùng cho endpoint GET /health/dependencies.

    Returns dict với các trường: url, status, response_time_ms, note
    """
    if _is_placeholder(base_url):
        return {
            "url": base_url,
            "status": "not_configured",
            "response_time_ms": None,
            "note": f"Chưa cấu hình URL trong .env. Điền {service_name.upper().replace(' ', '_')}_BASE_URL khi có IP thật."
        }

    health_url = f"{base_url.rstrip('/')}{health_path}"
    start = time.time()
    try:
        resp = requests.get(health_url, timeout=3)
        elapsed = round((time.time() - start) * 1000)
        if resp.status_code < 400:
            return {
                "url": health_url,
                "status": "reachable",
                "response_time_ms": elapsed,
                "http_status": resp.status_code,
                "note": "Kết nối thành công"
            }
        else:
            return {
                "url": health_url,
                "status": "error",
                "response_time_ms": elapsed,
                "http_status": resp.status_code,
                "note": f"Service trả về lỗi HTTP {resp.status_code}"
            }
    except requests.exceptions.ConnectionError:
        elapsed = round((time.time() - start) * 1000)
        return {
            "url": health_url,
            "status": "unreachable",
            "response_time_ms": elapsed,
            "note": "Không thể kết nối. Kiểm tra IP/port và đảm bảo cùng mạng."
        }
    except requests.exceptions.Timeout:
        elapsed = round((time.time() - start) * 1000)
        return {
            "url": health_url,
            "status": "timeout",
            "response_time_ms": elapsed,
            "note": "Kết nối timeout sau 3 giây"
        }
    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        return {
            "url": health_url,
            "status": "error",
            "response_time_ms": elapsed,
            "note": str(e)
        }


# ============================================================
# Helper nội bộ — Gửi HTTP POST với retry
# ============================================================
def _http_post(service_name: str, url: str, payload: Dict, timeout: int = 5, retries: int = 2) -> str:
    """
    Gửi HTTP POST tới service khác. Có retry và log chi tiết.
    """
    for attempt in range(retries + 1):
        try:
            app_logger.info(json.dumps({
                "event": "outbound_http_post",
                "service": service_name,
                "url": url,
                "attempt": attempt + 1
            }))
            response = requests.post(url, json=payload, timeout=timeout)
            if response.status_code in [200, 201, 202, 204]:
                app_logger.info(json.dumps({
                    "event": "outbound_http_success",
                    "service": service_name,
                    "status_code": response.status_code
                }))
                return "success"
            else:
                app_logger.warning(json.dumps({
                    "event": "outbound_http_bad_status",
                    "service": service_name,
                    "status_code": response.status_code,
                    "body": response.text[:200]
                }))
        except requests.exceptions.ConnectionError as e:
            app_logger.warning(json.dumps({
                "event": "outbound_http_connection_error",
                "service": service_name,
                "url": url,
                "attempt": attempt + 1,
                "error": str(e)
            }))
        except requests.exceptions.Timeout:
            app_logger.warning(json.dumps({
                "event": "outbound_http_timeout",
                "service": service_name,
                "url": url,
                "attempt": attempt + 1
            }))
        except Exception as e:
            app_logger.error(json.dumps({
                "event": "outbound_http_exception",
                "service": service_name,
                "url": url,
                "error": str(e)
            }))

        # Đợi trước khi retry (chỉ nếu còn lần thử)
        if attempt < retries:
            time.sleep(1)

    app_logger.error(json.dumps({
        "event": "outbound_http_all_attempts_failed",
        "service": service_name,
        "url": url,
        "total_attempts": retries + 1
    }))
    return "failed"
