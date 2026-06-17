from fastapi import APIRouter, HTTPException, Query, Header, Request, Depends, status
from typing import List, Optional, Dict, Any
import time
import uuid
from src.services.notification import notification_engine, config_service
from src.services import integration as integration_svc
from src.models.alert import (
    HealthStatus, AlertEventPayload, EventAcceptedResponse, NotificationLogItem,
    AlertTriggerPayload, TriggerAcceptedResponse
)

router = APIRouter(tags=["Notification Service APIs"])

# Định nghĩa lỗi Problem Exception dùng chung
class ProblemException(Exception):
    def __init__(self, status_code: int, type_uri: str, title: str, detail: str, instance: str):
        self.status_code = status_code
        self.content = {
            "type": type_uri,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance
        }

# Dependency để kiểm tra Bearer Authorization
def verify_bearer_auth(request: Request, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise ProblemException(
            status_code=401,
            type_uri="https://campus.local/errors/unauthorized",
            title="Sai hoặc thiếu thông tin định danh Bearer Token tại Header",
            detail="Header Authorization phải chứa token hợp lệ dạng 'Bearer <JWT_TOKEN>'",
            instance=request.url.path
        )
    return authorization


# 1. GET /health (Public)
@router.get("/health", response_model=HealthStatus)
def get_health(request: Request):
    """
    Kiểm tra trạng thái hoạt động của Notification Service.
    """
    iso_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "status": "ok",
        "service": "notification-service",
        "time": iso_timestamp
    }


# 1b. GET /health/dependencies (Public) — Kiểm tra kết nối tới các service khác
@router.get("/health/dependencies")
def get_health_dependencies():
    """
    Kiểm tra trạng thái kết nối tới các service khác trong hệ thống.
    Trả về 'not_configured' nếu URL chưa điền, 'reachable' nếu kết nối được.
    """
    import os
    b6_url = os.getenv("B6_BASE_URL", "")
    analytics_url = os.getenv("ANALYTICS_BASE_URL", "")
    gateway_url = os.getenv("API_GATEWAY_URL", "")

    return {
        "service": "notification-service-b7",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dependencies": {
            "core_business_b6": {
                **integration_svc.check_service_health("Core Business B6", b6_url, "/health"),
                "mock_mode": os.getenv("MOCK_B6_CALLBACK", "true").lower() == "true",
                "purpose": "Nhận cảnh báo đầu vào + gửi callback xác nhận sau khi thông báo",
                "how_to_connect": "Sửa B6_BASE_URL và MOCK_B6_CALLBACK=false trong .env"
            },
            "analytics_service": {
                **integration_svc.check_service_health("Analytics Service", analytics_url, "/health"),
                "mock_mode": os.getenv("MOCK_ANALYTICS", "true").lower() == "true",
                "purpose": "Nhận log thông báo để phân tích và vẽ biểu đồ",
                "how_to_connect": "Sửa ANALYTICS_BASE_URL và MOCK_ANALYTICS=false trong .env"
            },
            "api_gateway": {
                **integration_svc.check_service_health("API Gateway", gateway_url, "/health"),
                "mock_mode": os.getenv("MOCK_GATEWAY", "true").lower() == "true",
                "purpose": "Nếu có Gateway chung, định tuyến request từ hệ thống vào service này",
                "how_to_connect": "Sửa API_GATEWAY_URL và MOCK_GATEWAY=false trong .env"
            }
        },
        "hint": "Tất cả kết nối được điều khiển qua file .env. Chỉ cần điền IP thật và đặt MOCK_*=false."
    }

# 2. POST /notifications/events (Yêu cầu Bearer Auth, trả về 202)
@router.post("/notifications/events", status_code=202, response_model=EventAcceptedResponse, dependencies=[Depends(verify_bearer_auth)])
def receive_alert_event(
    request: Request,
    alert: AlertEventPayload,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Nhận event cảnh báo từ Core Business (B6).
    Tích hợp cơ chế chống trùng lặp bằng eventId và Idempotency-Key.
    """
    # 1. Kiểm tra trùng khóa Idempotency-Key trước tiên (nếu trùng trả về cached response 202)
    if idempotency_key:
        is_unique_key, cached_response = notification_engine.check_idempotency(idempotency_key)
        if not is_unique_key:
            return cached_response

    # 2. Kiểm tra trùng lặp eventId (nếu trùng trả về 409 Conflict)
    is_unique_event, event_reason = notification_engine.check_event_id_duplication(alert.eventId)
    if not is_unique_event:
        # Ghi log sự kiện chặn trùng
        notification_engine.record_log(
            event_id=alert.eventId,
            alert_id=alert.data.alertId,
            severity=alert.data.severity,
            message=alert.data.message,
            channel="none",
            sent=False,
            status="duplicate_ignored",
            error_msg=event_reason
        )
        raise ProblemException(
            status_code=409,
            type_uri="https://campus.local/errors/conflict",
            title="Sự kiện đã được xử lý trước đó",
            detail=event_reason,
            instance=request.url.path
        )

    # Xác định các kênh gửi tin
    target_channels = alert.data.channels
    if not target_channels:
        # Lấy mặc định các kênh đang active
        conf = config_service.config
        target_channels = []
        if conf["MOCK_TELEGRAM"] or conf["TELEGRAM_BOT_TOKEN"]:
            target_channels.append("telegram")
        if conf["MOCK_DISCORD"] or conf["DISCORD_WEBHOOK_URL"]:
            target_channels.append("discord")
        if conf["MOCK_EMAIL"] or (conf["SMTP_HOST"] and conf["SMTP_USERNAME"]):
            target_channels.append("email")
        
        target_channels.extend(["sms", "zalo"])

    # Chuẩn hóa danh sách kênh
    target_channels = list(set([c.lower().strip() for c in target_channels]))

    # Tạo một biên nhận UUID chung cho lượt trigger này
    ticket_id = str(uuid.uuid4())
    dispatched_channels = []
    statuses = []

    # Phân phối thông báo tới các kênh
    for chan in target_channels:
        # Nếu kênh không được định nghĩa trong OpenAPI enum
        if chan not in ["telegram", "email", "discord", "zalo", "sms"]:
            continue

        dispatched_channels.append(chan)
        result_log = notification_engine.send_notification(
            event_id=alert.eventId,
            alert_id=alert.data.alertId,
            severity=alert.data.severity,
            message=alert.data.message,
            target_user_id=alert.data.targetUserId,
            channel=chan,
            ticket_id=ticket_id
        )
        statuses.append(result_log["status"])

    # Tổng hợp trạng thái
    if not dispatched_channels:
        representative_status = "failed"
    elif all(s == "delivered" for s in statuses):
        representative_status = "delivered"
    elif all(s == "failed" for s in statuses):
        representative_status = "failed"
    else:
        representative_status = "partial"

    # Gọi ngược (Callback) báo cáo cho B6
    b6_callback_status = notification_engine.callback_to_b6(
        event_id=alert.eventId,
        ticket_id=ticket_id,
        status=representative_status,
        channels_dispatched=dispatched_channels
    )

    response_data = {
        "accepted": True,
        "eventId": alert.eventId,
        "ticket_id": ticket_id,
        "channels_dispatched": dispatched_channels,
        "status": representative_status,
        "b6_callback_status": b6_callback_status
    }

    # Đăng ký kết quả idempotency
    if idempotency_key:
        notification_engine.register_idempotency(idempotency_key, response_data)

    return response_data


# 2b. POST /notifications/trigger & POST /api/v1/alerts (Yêu cầu Bearer Auth, trả về 202)
def handle_trigger_alert(
    request: Request,
    alert: AlertTriggerPayload,
    idempotency_key: Optional[str],
):
    # 1. Kiểm tra trùng khóa Idempotency-Key trước tiên (nếu trùng trả về cached response 202)
    if idempotency_key:
        is_unique_key, cached_response = notification_engine.check_idempotency(idempotency_key)
        if not is_unique_key:
            return cached_response

    # 2. Kiểm tra trùng lặp alert_id (sử dụng như event_id)
    is_unique_event, event_reason = notification_engine.check_event_id_duplication(alert.alert_id)
    if not is_unique_event:
        # Ghi log sự kiện chặn trùng
        notification_engine.record_log(
            event_id=alert.alert_id,
            alert_id=alert.alert_id,
            severity=alert.severity,
            message=alert.message,
            channel="none",
            sent=False,
            status="duplicate_ignored",
            error_msg=event_reason
        )
        raise ProblemException(
            status_code=409,
            type_uri="https://campus.local/errors/conflict",
            title="Sự kiện đã được xử lý trước đó",
            detail=event_reason,
            instance=request.url.path
        )

    # Xác định các kênh gửi tin
    target_channels = alert.channels
    if not target_channels:
        conf = config_service.config
        target_channels = []
        if conf["MOCK_TELEGRAM"] or conf["TELEGRAM_BOT_TOKEN"]:
            target_channels.append("telegram")
        if conf["MOCK_DISCORD"] or conf["DISCORD_WEBHOOK_URL"]:
            target_channels.append("discord")
        if conf["MOCK_EMAIL"] or (conf["SMTP_HOST"] and conf["SMTP_USERNAME"]):
            target_channels.append("email")
        
        target_channels.extend(["sms", "zalo"])

    # Chuẩn hóa danh sách kênh
    target_channels = list(set([c.lower().strip() for c in target_channels]))

    # Tạo một biên nhận UUID chung cho lượt trigger này
    ticket_id = str(uuid.uuid4())
    dispatched_channels = []
    statuses = []

    # Phân phối thông báo tới các kênh
    for chan in target_channels:
        if chan not in ["telegram", "email", "discord", "zalo", "sms"]:
            continue

        dispatched_channels.append(chan)
        result_log = notification_engine.send_notification(
            event_id=alert.alert_id,
            alert_id=alert.alert_id,
            severity=alert.severity,
            message=alert.message,
            target_user_id=None,
            channel=chan,
            ticket_id=ticket_id
        )
        statuses.append(result_log["status"])

    # Tổng hợp trạng thái
    if not dispatched_channels:
        representative_status = "failed"
    elif all(s == "delivered" for s in statuses):
        representative_status = "delivered"
    elif all(s == "failed" for s in statuses):
        representative_status = "failed"
    else:
        representative_status = "partial"

    # Gọi ngược (Callback) báo cáo cho B6
    b6_callback_status = notification_engine.callback_to_b6(
        event_id=alert.alert_id,
        ticket_id=ticket_id,
        status=representative_status,
        channels_dispatched=dispatched_channels
    )

    sent = (representative_status == "delivered" or representative_status == "partial")
    
    response_data = {
        "sent": sent,
        "channel": dispatched_channels[0] if dispatched_channels else "telegram",
        "status": representative_status,
        "ticket_id": ticket_id
    }

    # Đăng ký kết quả idempotency
    if idempotency_key:
        notification_engine.register_idempotency(idempotency_key, response_data)

    return response_data


@router.post("/notifications/trigger", status_code=202, response_model=TriggerAcceptedResponse, dependencies=[Depends(verify_bearer_auth)])
def receive_trigger_alert_postman(
    request: Request,
    alert: AlertTriggerPayload,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Tiếp nhận alert từ Postman hoặc hệ thống kiểm thử với payload đơn giản (Dữ liệu đầu vào gợi ý của B7).
    """
    return handle_trigger_alert(request, alert, idempotency_key)


@router.post("/api/v1/alerts", status_code=202, response_model=TriggerAcceptedResponse, dependencies=[Depends(verify_bearer_auth)])
def receive_trigger_alert_legacy(
    request: Request,
    alert: AlertTriggerPayload,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Endpoint tương đương với /notifications/trigger nhưng sử dụng định tuyến cũ /api/v1/alerts được nêu trong README/Tài liệu tích hợp.
    """
    return handle_trigger_alert(request, alert, idempotency_key)


# 3. GET /notifications/logs (Yêu cầu Bearer Auth)
@router.get("/notifications/logs", dependencies=[Depends(verify_bearer_auth)])
def list_notification_logs(
    event_id: Optional[str] = Query(None, description="Lọc theo eventId của event từ B6"),
    channel: Optional[str] = Query(None, description="Lọc theo kênh gửi tin"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi tối đa trả về")
):
    """
    Cung cấp API tra cứu lịch sử gửi tin cho Analytics.
    Đầu ra tuân thủ nghiêm ngặt NotificationLogItem (additionalProperties: false, loại bỏ severity/message để tương thích với Postman).
    """
    logs = notification_engine.logs_db
    filtered = []

    for log in logs:
        # Áp dụng bộ lọc
        if event_id and log.get("event_id") != event_id:
            continue
        if channel and log.get("channel") != channel:
            continue
        
        # Lấy các trường log (loại bỏ severity và message theo yêu cầu kiểm thử Postman)
        log_item = {
            "ticket_id": log["ticket_id"],
            "event_id": log.get("event_id", ""),
            "alert_id": log["alert_id"],
            "channel": log["channel"],
            "status": log["status"],
            "retry_count": log["retry_count"],
            "error_message": log["error_message"],
            "timestamp": log["timestamp"]
        }
        filtered.append(log_item)
        if len(filtered) >= limit:
            break

    return {"items": filtered}


# 4. GET /api/v1/alerts/logs (Kênh nội bộ dành riêng cho Dashboard hiển thị đầy đủ thông tin)
@router.get("/api/v1/alerts/logs")
def get_dashboard_logs(limit: int = 50):
    """
    Endpoint nội bộ trả về toàn bộ trường log để Dashboard hiển thị giao diện đẹp mắt.
    """
    return notification_engine.logs_db[:limit]
