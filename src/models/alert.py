from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal, Union

class HealthStatus(BaseModel):
    status: str = Field(..., example="ok")
    service: str = Field(..., example="notification-service")
    time: str = Field(..., example="2026-05-10T08:00:00Z")

class AlertEventData(BaseModel):
    alertId: str = Field(..., description="UUID của alert phía B6")
    severity: str = Field(..., description="Mức độ nghiêm trọng (LOW, MEDIUM, HIGH, CRITICAL)")
    message: str = Field(..., min_length=5, max_length=500, description="Nội dung cảnh báo")
    targetUserId: Optional[str] = Field(None, description="ID sinh viên / người dùng liên quan (nếu có)")
    channels: Optional[List[str]] = Field(None, description="Danh sách kênh B6 yêu cầu B7 gửi (tùy chọn)")

class AlertEventPayload(BaseModel):
    eventId: str = Field(..., description="UUID của event — B7 dùng để chống gửi SMS/Telegram trùng lặp")
    eventType: str = Field(..., description="Loại event — phải là core.alert.created")
    occurredAt: str = Field(..., description="Thời điểm event xảy ra phía B6")
    correlationId: Optional[str] = Field(None, description="ID để trace log toàn hệ thống (tùy chọn)")
    source: str = Field(..., description="Service nguồn phát event")
    data: AlertEventData

class EventAcceptedResponse(BaseModel):
    accepted: bool = Field(..., example=True)
    eventId: str = Field(..., example="0196fb3d-4ad7-7d1e-9f49-5d5148d2babc")
    ticket_id: str = Field(..., example="0196fb3e-5ba2-7e2f-8a11-6d7249e3cade")
    channels_dispatched: List[str] = Field(..., example=["telegram", "discord"])
    status: str = Field(..., example="delivered")
    b6_callback_status: Optional[str] = Field(None, example="success")

class NotificationLogItem(BaseModel):
    ticket_id: str
    event_id: str
    alert_id: str
    channel: str
    status: str
    retry_count: int
    error_message: Optional[str] = None
    timestamp: str
    severity: Optional[str] = None
    message: Optional[str] = None

class AlertTriggerPayload(BaseModel):
    alert_id: str = Field(..., description="UUID hoặc định danh của alert truyền từ Core Business")
    severity: str = Field(..., description="Mức độ nghiêm trọng (LOW, MEDIUM, HIGH, CRITICAL)")
    message: str = Field(..., min_length=5, max_length=500, description="Nội dung cảnh báo")
    target: str = Field(..., description="Nhóm chức năng tiếp nhận (ví dụ: security_team)")
    channels: Optional[List[str]] = Field(None, description="Danh sách kênh B6 yêu cầu B7 gửi (tùy chọn)")

class TriggerAcceptedResponse(BaseModel):
    sent: bool = Field(..., example=True)
    channel: str = Field(..., example="telegram")
    status: str = Field(..., example="delivered")
    ticket_id: str = Field(..., example="0196fb3e-5ba2-7e2f-8a11-6d7249e3cade")


# ============================================================
# Analytics Export Models — Hứng dữ liệu inbound từ B6
# ============================================================

class AccessLogDetails(BaseModel):
    """Chi tiết sự kiện quẹt thẻ sinh viên."""
    uid: str = Field(..., description="UID thẻ RFID của sinh viên")
    student_id: str = Field(..., description="Mã số sinh viên")
    class_name: Optional[str] = Field(None, description="Lớp học của sinh viên")
    gate_id: str = Field(..., description="Cổng ra vào (ví dụ: GATE-A)")
    action: str = Field(..., description="Kết quả: GRANTED hoặc DENIED")


class FireAlarmLogDetails(BaseModel):
    """Chi tiết sự kiện báo cháy / nhiệt độ bất thường."""
    device_id: str = Field(..., description="ID thiết bị cảm biến (ví dụ: esp32-lab-a101)")
    location: str = Field(..., description="Vị trí phòng / khu vực")
    temperature: Optional[float] = Field(None, description="Nhiệt độ đo được (°C)")
    action: str = Field(..., description="Hành động kích hoạt (ví dụ: EVACUATION_TRIGGERED)")


class AnalyticsLogItem(BaseModel):
    """Một mục log trong batch xuất dữ liệu từ B6."""
    log_type: str = Field(..., description="Loại log: ACCESS | FIRE_ALARM")
    timestamp: str = Field(..., description="Thời điểm xảy ra sự kiện (ISO 8601)")
    details: Dict[str, Any] = Field(..., description="Chi tiết tuỳ theo log_type")


class AnalyticsExportPayload(BaseModel):
    """Payload đầy đủ B6 gửi sang (batch export analytics log)."""
    from_time: Optional[str] = Field(None, alias="from", description="Mốc thời gian bắt đầu khoảng export")
    to_time: Optional[str] = Field(None, alias="to", description="Mốc thời gian kết thúc khoảng export")
    data: List[AnalyticsLogItem] = Field(..., description="Danh sách các log event cần xử lý")

    model_config = {"populate_by_name": True}


class AnalyticsExportItemResult(BaseModel):
    """Kết quả xử lý cho từng log item trong batch."""
    log_type: str
    timestamp: str
    notification_triggered: bool
    ticket_id: Optional[str] = None
    channels_dispatched: Optional[List[str]] = None
    reason: str


class AnalyticsExportResponse(BaseModel):
    """Response trả về sau khi xử lý batch analytics export từ B6."""
    accepted: bool
    received_from: str = Field("direct-demo", description="Nguồn gửi (core-business-b6 hoặc direct-demo khi test độc lập)")
    total_received: int
    notifications_triggered: int
    results: List[AnalyticsExportItemResult]
