from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from src.services.notification import config_service

router = APIRouter(prefix="/api/v1/channels", tags=["Notification Channels"])

class ChannelConfigUpdate(BaseModel):
    DEDUPLICATION_TTL_SECONDS: Optional[int] = Field(None, description="Thời gian lưu alert_id để chống trùng lặp (giây)")
    RETRY_MAX_LIMIT: Optional[int] = Field(None, description="Số lần thử lại tối đa khi gửi lỗi")
    RETRY_DELAY_SECONDS: Optional[int] = Field(None, description="Thời gian chờ giữa các lần thử lại (giây)")
    
    MOCK_TELEGRAM: Optional[bool] = Field(None, description="Chế độ giả lập kênh Telegram")
    MOCK_DISCORD: Optional[bool] = Field(None, description="Chế độ giả lập kênh Discord")
    MOCK_EMAIL: Optional[bool] = Field(None, description="Chế độ giả lập kênh Email")
    MOCK_SMS: Optional[bool] = Field(None, description="Chế độ giả lập kênh SMS")
    MOCK_ZALO: Optional[bool] = Field(None, description="Chế độ giả lập kênh Zalo")

    TELEGRAM_BOT_TOKEN: Optional[str] = Field(None, description="Token của Telegram Bot")
    TELEGRAM_CHAT_ID: Optional[str] = Field(None, description="Chat ID của Telegram Group/User")

    DISCORD_WEBHOOK_URL: Optional[str] = Field(None, description="URL Discord Webhook")

    SMTP_HOST: Optional[str] = Field(None, description="Địa chỉ máy chủ SMTP")
    SMTP_PORT: Optional[int] = Field(None, description="Cổng kết nối máy chủ SMTP")
    SMTP_USERNAME: Optional[str] = Field(None, description="Tên đăng nhập SMTP")
    SMTP_PASSWORD: Optional[str] = Field(None, description="Mật khẩu ứng dụng SMTP")
    SMTP_SENDER: Optional[str] = Field(None, description="Địa chỉ email người gửi")
    SMTP_RECEIVER: Optional[str] = Field(None, description="Địa chỉ email người nhận")

@router.get("")
def get_channels():
    """
    Lấy thông tin trạng thái hoạt động hiện tại của các kênh thông báo.
    """
    conf = config_service.get_all()
    
    # Định dạng lại dữ liệu trả về cho dashboard trực quan hơn
    channels = {
        "telegram": {
            "name": "Telegram Bot",
            "mocked": conf["MOCK_TELEGRAM"],
            "configured": bool(conf["TELEGRAM_BOT_TOKEN"] and conf["TELEGRAM_CHAT_ID"]) or conf["MOCK_TELEGRAM"],
            "target_detail": conf["TELEGRAM_CHAT_ID"] if conf["TELEGRAM_CHAT_ID"] else "Not configured"
        },
        "discord": {
            "name": "Discord Webhook",
            "mocked": conf["MOCK_DISCORD"],
            "configured": bool(conf["DISCORD_WEBHOOK_URL"]) or conf["MOCK_DISCORD"],
            "target_detail": "Webhook URL" if conf["DISCORD_WEBHOOK_URL"] else "Not configured"
        },
        "email": {
            "name": "SMTP Email",
            "mocked": conf["MOCK_EMAIL"],
            "configured": bool(conf["SMTP_HOST"] and conf["SMTP_USERNAME"] and conf["SMTP_PASSWORD"]) or conf["MOCK_EMAIL"],
            "target_detail": conf["SMTP_RECEIVER"] if conf["SMTP_RECEIVER"] else "Not configured"
        },
        "sms": {
            "name": "SMS Mock Service",
            "mocked": conf["MOCK_SMS"],
            "configured": True,
            "target_detail": "SMS Mock Console Output"
        },
        "zalo": {
            "name": "Zalo Mock Service",
            "mocked": conf["MOCK_ZALO"],
            "configured": True,
            "target_detail": "Zalo Mock Console Output"
        }
    }
    
    return {
        "channels": channels,
        "global_settings": {
            "deduplication_ttl": conf["DEDUPLICATION_TTL_SECONDS"],
            "retry_limit": conf["RETRY_MAX_LIMIT"],
            "retry_delay": conf["RETRY_DELAY_SECONDS"]
        }
    }

@router.post("/configure")
def configure_channels(update_data: ChannelConfigUpdate):
    """
    Cập nhật động cấu hình của các kênh thông báo từ Dashboard.
    """
    # Lọc bỏ các giá trị None
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    
    config_service.update(update_dict)
    return {"status": "success", "message": "Configuration updated successfully", "updated_keys": list(update_dict.keys())}
