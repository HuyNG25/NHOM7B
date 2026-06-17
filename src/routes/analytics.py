"""
Route: POST /analytics/export
Hứng dữ liệu Analytics Log Export từ Core Business (B6).
Tự động phân loại và trigger thông báo tương ứng theo từng log_type.

Luồng xử lý:
  B6 → POST /analytics/export → B7 phân loại → Notification Engine → Kênh gửi đi

QUAN TRỌNG:
  Endpoint này KHÔNG yêu cầu Bearer token vì đây là giao tiếp Service-to-Service
  nội bộ (B6 → B7). Không phải request từ người dùng cuối.
  Nhận diện nguồn gửi qua header tuỳ chọn: X-Source-Service
  
  Chế độ hoạt động:
  - Demo độc lập: Gọi trực tiếp POST /analytics/export (không cần X-Source-Service)
  - Kết nối B6 thật: B6 truyền header X-Source-Service: core-business-b6 — B7 tự log nhận dạng
"""

from fastapi import APIRouter, Request, Header
from typing import List, Optional
import uuid
import time

from src.models.alert import (
    AnalyticsExportPayload,
    AnalyticsExportResponse,
    AnalyticsExportItemResult,
)
from src.services.notification import notification_engine, config_service
from src.utils.logger import app_logger

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics Export — Inbound từ B6"],
)

# ------------------------------------------------------------------ #
# Helpers: Xây dựng message notification từ từng loại log            #
# ------------------------------------------------------------------ #

def _build_access_message(details: dict) -> tuple[str, str]:
    """
    Trả về (message_text, severity) cho sự kiện quẹt thẻ.
    DENIED → HIGH (cần cảnh báo), GRANTED → LOW (chỉ ghi nhận).
    """
    action = details.get("action", "UNKNOWN").upper()
    student_id = details.get("student_id", "N/A")
    gate_id = details.get("gate_id", "N/A")
    class_name = details.get("class_name", "N/A")
    uid = details.get("uid", "N/A")

    if action == "DENIED":
        severity = "HIGH"
        message = (
            f"🚫 [TRUY CẬP BỊ TỪ CHỐI] Sinh viên {student_id} (Lớp: {class_name}) "
            f"đã bị chặn tại cổng {gate_id}. UID thẻ: {uid}. "
            f"Hành động: {action}. Cần kiểm tra ngay!"
        )
    else:
        severity = "LOW"
        message = (
            f"✅ [TRUY CẬP HỢP LỆ] Sinh viên {student_id} (Lớp: {class_name}) "
            f"đã vào qua cổng {gate_id}. UID: {uid}."
        )
    return message, severity


def _build_fire_alarm_message(details: dict) -> tuple[str, str]:
    """
    Trả về (message_text, severity) cho sự kiện báo cháy.
    Luôn ở mức CRITICAL vì liên quan đến an toàn tính mạng.
    """
    device_id = details.get("device_id", "N/A")
    location = details.get("location", "N/A")
    temperature = details.get("temperature")
    action = details.get("action", "N/A")

    temp_str = f"{temperature}°C" if temperature is not None else "N/A"
    severity = "CRITICAL"
    message = (
        f"🔥 [BÁO CHÁY KHẨN CẤP] Cảm biến {device_id} kích hoạt tại {location}! "
        f"Nhiệt độ đo được: {temp_str}. Hành động: {action}. "
        f"Yêu cầu sơ tán ngay lập tức!"
    )
    return message, severity


# ------------------------------------------------------------------ #
# Mapping log_type → hàm xử lý và điều kiện trigger notification    #
# ------------------------------------------------------------------ #

# Các log_type luôn trigger notification (bất kể action là gì)
ALWAYS_NOTIFY_TYPES = {"FIRE_ALARM"}

# Các action trong ACCESS log cần trigger notification
ACCESS_NOTIFY_ACTIONS = {"DENIED"}


def _should_trigger_notification(log_type: str, details: dict) -> bool:
    """Quyết định có cần gửi notification cho log item này không."""
    log_type_upper = log_type.upper()

    if log_type_upper in ALWAYS_NOTIFY_TYPES:
        return True

    if log_type_upper == "ACCESS":
        action = details.get("action", "").upper()
        return action in ACCESS_NOTIFY_ACTIONS

    # Các loại log khác chưa định nghĩa → không trigger
    return False


# ------------------------------------------------------------------ #
# Endpoint chính                                                       #
# ------------------------------------------------------------------ #

@router.post(
    "/export",
    status_code=202,
    response_model=AnalyticsExportResponse,
    summary="Nhận batch log export từ Core Business (B6)",
    description=(
        "**[S2S — Không cần Bearer Token]** "
        "Endpoint này được B6 gọi để gửi batch dữ liệu log khi có sinh viên quẹt thẻ "
        "hoặc có sự kiện báo cháy. B7 sẽ phân loại từng log item và tự động phát cảnh báo "
        "qua các kênh thông báo (Telegram, Discord, Email, v.v.) theo mức độ nghiêm trọng.\n\n"
        "- **Demo độc lập**: Gọi trực tiếp không cần header đặc biệt.\n"
        "- **Kết nối B6 thật**: B6 truyền thêm `X-Source-Service: core-business-b6`."
    ),
)
async def receive_analytics_export(
    request: Request,
    payload: AnalyticsExportPayload,
    x_source_service: Optional[str] = Header(None, alias="X-Source-Service"),
):
    """
    Xử lý batch analytics log export từ B6.

    - **ACCESS / DENIED** → Trigger notification mức HIGH
    - **ACCESS / GRANTED** → Chỉ ghi log, không gửi notification
    - **FIRE_ALARM** → Luôn trigger notification mức CRITICAL
    
    Header tùy chọn:
    - X-Source-Service: Nhận dạng nguồn gửi (ví dụ: core-business-b6)
      Nếu không có → coi là request demo/kiểm thử trực tiếp (vẫn hoạt động bình thường)
    """
    source_label = x_source_service or "direct-demo"
    app_logger.info(
        f"[analytics/export] Nhận batch {len(payload.data)} log(s) "
        f"từ {payload.from_time} đến {payload.to_time} "
        f"| nguồn: {source_label}"
    )

    results: List[AnalyticsExportItemResult] = []
    notifications_triggered = 0

    conf = config_service.config

    for item in payload.data:
        log_type = item.log_type.upper()
        details = item.details
        should_notify = _should_trigger_notification(log_type, details)

        if not should_notify:
            notification_engine.record_inbound_signal(
                log_type=log_type,
                timestamp=item.timestamp,
                details=details,
                status="normal",
                reason="Sự kiện bình thường — không cần gửi cảnh báo"
            )
            results.append(AnalyticsExportItemResult(
                log_type=log_type,
                timestamp=item.timestamp,
                notification_triggered=False,
                reason="Sự kiện bình thường — không cần gửi cảnh báo",
            ))
            continue

        # --- Xây dựng message và severity ---
        if log_type == "FIRE_ALARM":
            message, severity = _build_fire_alarm_message(details)
        elif log_type == "ACCESS":
            message, severity = _build_access_message(details)
        else:
            message = f"[{log_type}] Sự kiện bất thường: {details}"
            severity = "MEDIUM"

        # --- Tạo ID định danh ---
        _seed = f"{log_type}-{item.timestamp}-{details.get('uid') or details.get('device_id', '')}"
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, _seed))
        alert_id = str(uuid.uuid4())
        ticket_id = str(uuid.uuid4())

        # --- Kiểm tra deduplication ---
        is_unique, dup_reason = notification_engine.check_event_id_duplication(event_id)
        if not is_unique:
            notification_engine.record_inbound_signal(
                log_type=log_type,
                timestamp=item.timestamp,
                details=details,
                status="duplicate",
                reason=f"Trùng lặp — bỏ qua: {dup_reason}"
            )
            results.append(AnalyticsExportItemResult(
                log_type=log_type,
                timestamp=item.timestamp,
                notification_triggered=False,
                reason=f"Trùng lặp — bỏ qua: {dup_reason}",
            ))
            continue

        # --- Xác định kênh gửi ---
        target_channels = []
        if conf["MOCK_TELEGRAM"] or conf["TELEGRAM_BOT_TOKEN"]:
            target_channels.append("telegram")
        if conf["MOCK_DISCORD"] or conf["DISCORD_WEBHOOK_URL"]:
            target_channels.append("discord")
        if conf["MOCK_EMAIL"] or (conf["SMTP_HOST"] and conf["SMTP_USERNAME"]):
            target_channels.append("email")
        target_channels.extend(["sms", "zalo"])
        target_channels = list(set(target_channels))

        dispatched_channels = []
        statuses = []

        for chan in target_channels:
            if chan not in ["telegram", "email", "discord", "zalo", "sms"]:
                continue
            dispatched_channels.append(chan)
            result_log = notification_engine.send_notification(
                event_id=event_id,
                alert_id=alert_id,
                severity=severity,
                message=message,
                target_user_id=details.get("student_id") or details.get("device_id"),
                channel=chan,
                ticket_id=ticket_id,
            )
            statuses.append(result_log["status"])

        if all(s == "delivered" for s in statuses):
            rep_status = "delivered"
        elif all(s == "failed" for s in statuses):
            rep_status = "failed"
        else:
            rep_status = "partial"

        notifications_triggered += 1

        notification_engine.record_inbound_signal(
            log_type=log_type,
            timestamp=item.timestamp,
            details=details,
            status="triggered",
            reason=f"Đã phát thông báo ({rep_status}) — mức {severity}"
        )

        results.append(AnalyticsExportItemResult(
            log_type=log_type,
            timestamp=item.timestamp,
            notification_triggered=True,
            ticket_id=ticket_id,
            channels_dispatched=dispatched_channels,
            reason=f"Notification dispatched ({rep_status}) — severity: {severity}",
        ))

    app_logger.info(
        f"[analytics/export] Xong. Triggered {notifications_triggered}/{len(payload.data)} notification(s)."
    )

    return AnalyticsExportResponse(
        accepted=True,
        received_from=source_label,
        total_received=len(payload.data),
        notifications_triggered=notifications_triggered,
        results=results,
    )


@router.get("/inbound/signals")
def get_inbound_signals(limit: int = 50):
    return notification_engine.inbound_signals_db[:limit]
