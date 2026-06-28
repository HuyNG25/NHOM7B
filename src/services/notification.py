import os
import time
import json
import smtplib
import uuid
import asyncio
from email.mime.text import MIMEText
from email.header import Header
import requests
from typing import Dict, List, Tuple, Any, Optional
from src.utils.logger import app_logger
from src.services import integration as integration_svc

# ============================================================
# EventBus — Pub/Sub queue để push dữ liệu real-time qua SSE
# ============================================================
class EventBus:
    """
    Quản lý danh sách subscriber (asyncio.Queue) đang lắng nghe.
    Được cập nhật để đảm bảo Thread-safe (khi gọi từ BackgroundTasks).
    """
    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []
        self._loop = None

    def subscribe(self) -> asyncio.Queue:
        """Client SSE mới kết nối — trả về queue riêng của họ."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Client SSE ngắt kết nối — xoá khỏi danh sách."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Gửi sự kiện tới tất cả subscriber đang hoạt động.
        Sử dụng call_soon_threadsafe để tránh lỗi asyncio từ BackgroundTasks thread.
        """
        payload = json.dumps({"type": event_type, "data": data})
        
        def _do_publish():
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self.unsubscribe(q)
                
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(_do_publish)
        else:
            _do_publish()

# Instance toàn cục — dùng chung giữa routes và services
event_bus = EventBus()

# Cấu hình mặc định từ .env
DEFAULT_CONFIG = {
    "DEDUPLICATION_TTL_SECONDS": int(os.getenv("DEDUPLICATION_TTL_SECONDS", 300)),
    "RETRY_MAX_LIMIT": int(os.getenv("RETRY_MAX_LIMIT", 3)),
    "RETRY_DELAY_SECONDS": int(os.getenv("RETRY_DELAY_SECONDS", 2)),
    
    "MOCK_TELEGRAM": os.getenv("MOCK_TELEGRAM", "true").lower() == "true",
    "MOCK_DISCORD": os.getenv("MOCK_DISCORD", "true").lower() == "true",
    "MOCK_EMAIL": os.getenv("MOCK_EMAIL", "true").lower() == "true",
    "MOCK_SMS": os.getenv("MOCK_SMS", "true").lower() == "true",
    "MOCK_ZALO": os.getenv("MOCK_ZALO", "true").lower() == "true",

    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),

    "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", ""),

    "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "SMTP_PORT": int(os.getenv("SMTP_PORT", 587)),
    "SMTP_USERNAME": os.getenv("SMTP_USERNAME", ""),
    "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
    "SMTP_SENDER": os.getenv("SMTP_SENDER", ""),
    "SMTP_RECEIVER": os.getenv("SMTP_RECEIVER", ""),

    "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "TWILIO_FROM_NUMBER": os.getenv("TWILIO_FROM_NUMBER", ""),
    "SMS_RECEIVER_NUMBER": os.getenv("SMS_RECEIVER_NUMBER", ""),

    "ZALO_OA_TOKEN": os.getenv("ZALO_OA_TOKEN", ""),
    "ZALO_RECEIVER_ID": os.getenv("ZALO_RECEIVER_ID", ""),

    # Core Business (B6) Callback settings
    "B6_BASE_URL": os.getenv("B6_BASE_URL", ""),
    "MOCK_B6_CALLBACK": os.getenv("MOCK_B6_CALLBACK", "true").lower() == "true",

    # Analytics Service settings
    "ANALYTICS_BASE_URL": os.getenv("ANALYTICS_BASE_URL", ""),
    "MOCK_ANALYTICS": os.getenv("MOCK_ANALYTICS", "true").lower() == "true",
}

class ConfigurationService:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()

    def get_all(self) -> Dict[str, Any]:
        return self.config

    def update(self, new_config: Dict[str, Any]) -> None:
        for key, value in new_config.items():
            if key in self.config:
                # Đảm bảo giữ đúng kiểu dữ liệu (int, bool, str)
                if isinstance(self.config[key], bool):
                    if isinstance(value, str):
                        self.config[key] = value.lower() == "true"
                    else:
                        self.config[key] = bool(value)
                elif isinstance(self.config[key], int):
                    self.config[key] = int(value)
                else:
                    self.config[key] = str(value)
        app_logger.info(json.dumps({
            "event": "config_updated",
            "message": "System configuration updated successfully"
        }))

# Instance toàn cục để lưu trữ config động
config_service = ConfigurationService()

class NotificationEngine:
    def __init__(self):
        pass

    @property
    def logs_db(self) -> List[Dict[str, Any]]:
        from src.utils.database import db_manager
        query = "SELECT * FROM notification_logs ORDER BY timestamp DESC LIMIT 100"
        rows = db_manager.execute_read(query)
        for r in rows:
            r["sent"] = r["status"] in ["delivered", "partial"]
        return rows

    @property
    def inbound_signals_db(self) -> List[Dict[str, Any]]:
        from src.utils.database import db_manager
        query = "SELECT * FROM inbound_signals ORDER BY timestamp DESC LIMIT 100"
        rows = db_manager.execute_read(query)
        for r in rows:
            if isinstance(r["details"], str):
                try:
                    r["details"] = json.loads(r["details"])
                except Exception:
                    pass
        return rows

    def record_inbound_signal(self, log_type: str, timestamp: str, details: Dict[str, Any], status: str, reason: str) -> None:
        """
        Lưu vết các tín hiệu gửi từ B6 qua endpoint /analytics/export vào PostgreSQL.
        Đồng thời publish sự kiện SSE để Dashboard hiển thị real-time.
        """
        from src.utils.database import db_manager
        query = """
            INSERT INTO inbound_signals (log_type, timestamp, details, status, reason)
            VALUES (%s, %s, %s, %s, %s)
        """
        db_manager.execute_write(query, (log_type, timestamp, json.dumps(details), status, reason))

        # Publish real-time event tới tất cả SSE client
        event_bus.publish("inbound_signal", {
            "log_type": log_type,
            "timestamp": timestamp,
            "details": details,
            "status": status,
            "reason": reason
        })

    def check_event_id_duplication(self, event_id: str) -> Tuple[bool, str]:
        """
        Kiểm tra trùng lặp eventId từ PostgreSQL.
        """
        from src.utils.database import db_manager
        current_time = time.time()
        ttl = config_service.config["DEDUPLICATION_TTL_SECONDS"]

        # Dọn dẹp cache quá hạn
        cleanup_query = "DELETE FROM event_dedup_cache WHERE %s - received_at > %s"
        db_manager.execute_write(cleanup_query, (current_time, ttl))

        # Kiểm tra trùng lặp
        query = "SELECT received_at FROM event_dedup_cache WHERE event_id = %s"
        rows = db_manager.execute_read(query, (event_id,))
        if rows:
            time_passed = current_time - rows[0]["received_at"]
            return False, f"Duplicate event ID detected. Received {int(time_passed)}s ago (TTL: {ttl}s)."

        # Lưu mới
        insert_query = "INSERT INTO event_dedup_cache (event_id, received_at) VALUES (%s, %s) ON CONFLICT (event_id) DO NOTHING"
        db_manager.execute_write(insert_query, (event_id, current_time))
        return True, "Unique event"

    def check_idempotency(self, idempotency_key: str) -> Tuple[bool, Any]:
        """
        Kiểm tra trùng lặp khóa Idempotency-Key từ PostgreSQL.
        """
        from src.utils.database import db_manager
        current_time = time.time()
        ttl = config_service.config["DEDUPLICATION_TTL_SECONDS"]

        # Dọn dẹp quá hạn
        cleanup_query = "DELETE FROM idempotency_cache WHERE %s - created_at > %s"
        db_manager.execute_write(cleanup_query, (current_time, ttl))

        # Kiểm tra tồn tại
        query = "SELECT response_data FROM idempotency_cache WHERE idempotency_key = %s"
        rows = db_manager.execute_read(query, (idempotency_key,))
        if rows:
            return False, rows[0]["response_data"]

        return True, None

    def register_idempotency(self, idempotency_key: str, response: Any) -> None:
        """
        Đăng ký kết quả xử lý của một Idempotency-Key vào PostgreSQL.
        """
        from src.utils.database import db_manager
        query = """
            INSERT INTO idempotency_cache (idempotency_key, response_data, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (idempotency_key) DO UPDATE SET response_data = EXCLUDED.response_data, created_at = EXCLUDED.created_at
        """
        db_manager.execute_write(query, (idempotency_key, json.dumps(response), time.time()))

    def record_log(self, event_id: str, alert_id: str, severity: str, message: str, 
                   channel: str, sent: bool, status: str, error_msg: str = "", 
                   retry_count: int = 0, ticket_id: str = None) -> Dict[str, Any]:
        """
        Ghi log trạng thái gửi thông báo vào CSDL PostgreSQL, console và file.
        """
        from src.utils.database import db_manager
        # Định dạng thời gian theo chuẩn ISO 8601 UTC
        iso_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        t_id = ticket_id or str(uuid.uuid4())

        log_entry = {
            "ticket_id": t_id,
            "event_id": event_id,
            "alert_id": alert_id,
            "channel": channel,
            "status": status,
            "retry_count": retry_count,
            "error_message": error_msg if error_msg else None,
            "timestamp": iso_timestamp,
            "severity": severity,
            "message": message,
            "sent": sent
        }

        # Lưu vào PostgreSQL
        query = """
            INSERT INTO notification_logs (ticket_id, event_id, alert_id, channel, status, retry_count, error_message, timestamp, severity, message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticket_id) DO NOTHING
        """
        db_manager.execute_write(query, (
            t_id, event_id, alert_id, channel, status, retry_count, 
            error_msg if error_msg else None, iso_timestamp, severity, message
        ))

        # Ghi log bằng logger hệ thống (file & console)
        app_logger.info(json.dumps(log_entry))

        # Đẩy log sang Analytics Service (nếu đã cấu hình)
        integration_svc.push_log_to_analytics(log_entry)

        # Publish real-time event tới tất cả SSE client trên Dashboard
        event_bus.publish("notification_log", log_entry)

        return log_entry

    def send_notification(self, event_id: str, alert_id: str, severity: str, message: str, 
                          target_user_id: Optional[str], channel: str, ticket_id: str = None) -> Dict[str, Any]:
        """
        Gửi thông báo qua một kênh cụ thể với cơ chế Retry.
        """
        conf = config_service.config
        max_retries = conf["RETRY_MAX_LIMIT"]
        base_delay = conf["RETRY_DELAY_SECONDS"]
        t_id = ticket_id or str(uuid.uuid4())

        # 1. Xác định kênh có bị mock hay không
        mock_key = f"MOCK_{channel.upper()}"
        is_mocked = conf.get(mock_key, True)

        for attempt in range(max_retries + 1):
            try:
                if is_mocked:
                    # Chế độ Mock: thành công ngay lập tức sau khi log giả lập
                    app_logger.info(json.dumps({
                        "event": "mock_notification",
                        "channel": channel,
                        "message": f"Simulated delivery of event {event_id} / alert {alert_id} via {channel}"
                    }))
                    return self.record_log(event_id, alert_id, severity, message, channel, True, "delivered", retry_count=attempt, ticket_id=t_id)
                
                # Chế độ thật: Thực hiện kết nối mạng
                if channel == "telegram":
                    self._dispatch_telegram(conf["TELEGRAM_BOT_TOKEN"], conf["TELEGRAM_CHAT_ID"], event_id, alert_id, severity, message, target_user_id)
                elif channel == "discord":
                    self._dispatch_discord(conf["DISCORD_WEBHOOK_URL"], event_id, alert_id, severity, message, target_user_id)
                elif channel == "email":
                    self._dispatch_email(
                        conf["SMTP_HOST"], conf["SMTP_PORT"], 
                        conf["SMTP_USERNAME"], conf["SMTP_PASSWORD"],
                        conf["SMTP_SENDER"], conf["SMTP_RECEIVER"],
                        event_id, alert_id, severity, message, target_user_id
                    )
                elif channel == "sms":
                    self._dispatch_sms(
                        conf["TWILIO_ACCOUNT_SID"], conf["TWILIO_AUTH_TOKEN"], 
                        conf["TWILIO_FROM_NUMBER"], conf["SMS_RECEIVER_NUMBER"],
                        event_id, alert_id, severity, message, target_user_id
                    )
                elif channel == "zalo":
                    self._dispatch_zalo(
                        conf["ZALO_OA_TOKEN"], conf["ZALO_RECEIVER_ID"],
                        event_id, alert_id, severity, message, target_user_id
                    )
                else:
                    raise ValueError(f"Real connection for channel '{channel}' is not implemented.")

                # Thành công
                return self.record_log(event_id, alert_id, severity, message, channel, True, "delivered", retry_count=attempt, ticket_id=t_id)

            except Exception as e:
                error_msg = str(e)
                app_logger.warning(json.dumps({
                    "event": "notification_attempt_failed",
                    "channel": channel,
                    "event_id": event_id,
                    "alert_id": alert_id,
                    "attempt": attempt,
                    "error": error_msg
                }))

                if attempt < max_retries:
                    # Tính toán backoff delay: delay * 2^attempt
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    # Hết lượt retry
                    return self.record_log(event_id, alert_id, severity, message, channel, False, "failed", error_msg=error_msg, retry_count=attempt, ticket_id=t_id)

    def callback_to_b6(self, event_id: str, ticket_id: str, status: str, channels_dispatched: List[str]) -> str:
        """
        Gọi ngược tới Core Business (B6) để báo cáo trạng thái gửi tin.
        Uỷ quyền cho integration_svc để xử lý mock/thật tự động.
        Trả về: "mocked" | "success" | "failed"
        """
        return integration_svc.call_b6_callback(
            event_id=event_id,
            ticket_id=ticket_id,
            status=status,
            channels_dispatched=channels_dispatched
        )

    # --- Các hàm Helper Dispatch gửi đi thật ---
    def _dispatch_telegram(self, token: str, chat_id: str, event_id: str, alert_id: str, severity: str, message: str, target_user_id: Optional[str]):
        if not token or not chat_id:
            raise ValueError("Telegram Bot Token or Chat ID is missing.")
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        emoji = "🔴" if severity.lower() == "high" else ("⚠️" if severity.lower() == "medium" else "ℹ️")
        
        formatted_message = (
            f"{emoji} *SYSTEM ALERT ({severity.upper()})*\n"
            f"*Alert ID:* `{alert_id}`\n"
            f"*Event ID:* `{event_id}`\n"
            f"*Target User:* {target_user_id or 'N/A'}\n"
            f"*Time:* {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"*Message:* {message}"
        )
        
        payload = {
            "chat_id": chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code != 200:
            raise RuntimeError(f"Telegram API returned status {response.status_code}: {response.text}")

    def _dispatch_discord(self, webhook_url: str, event_id: str, alert_id: str, severity: str, message: str, target_user_id: Optional[str]):
        if not webhook_url:
            raise ValueError("Discord Webhook URL is missing.")

        color = 16711680 if severity.lower() == "high" else (16776960 if severity.lower() == "medium" else 65280)
        
        payload = {
            "embeds": [
                {
                    "title": f"🚨 Alert Detected: {severity.upper()}",
                    "color": color,
                    "fields": [
                        {"name": "Alert ID", "value": alert_id, "inline": True},
                        {"name": "Event ID", "value": event_id, "inline": True},
                        {"name": "Target User ID", "value": target_user_id or "N/A", "inline": True},
                        {"name": "Timestamp", "value": time.strftime('%Y-%m-%d %H:%M:%S'), "inline": False},
                        {"name": "Message Description", "value": message, "inline": False}
                    ],
                    "footer": {
                        "text": "Notification Service | FIT4110"
                    }
                }
            ]
        }

        response = requests.post(webhook_url, json=payload, timeout=8)
        if response.status_code not in [200, 204]:
            raise RuntimeError(f"Discord API returned status {response.status_code}: {response.text}")

    def _dispatch_email(self, host: str, port: int, username: str, password: str, 
                        sender: str, receiver: str, event_id: str, alert_id: str, severity: str, message: str, target_user_id: Optional[str]):
        if not host or not username or not password or not sender or not receiver:
            raise ValueError("Email SMTP settings are incomplete.")

        emoji = "🔴" if severity.lower() == "high" else ("⚠️" if severity.lower() == "medium" else "ℹ️")
        subject = f"{emoji} [{severity.upper()}] Notification Alert - {alert_id}"
        
        body = (
            f"Notification Service Alert\n"
            f"-----------------------------------------\n"
            f"Alert ID: {alert_id}\n"
            f"Event ID: {event_id}\n"
            f"Severity: {severity.upper()}\n"
            f"Target User: {target_user_id or 'N/A'}\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"-----------------------------------------\n"
            f"Message: {message}\n"
        )
        
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = sender
        msg['To'] = receiver

        # Sử dụng SMTP hoặc SMTP_SSL dựa trên port
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()

        server.login(username, password)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()

    def _dispatch_sms(self, account_sid: str, auth_token: str, from_number: str, receiver_number: str, event_id: str, alert_id: str, severity: str, message: str, target_user_id: Optional[str]):
        if not account_sid or not auth_token or not from_number or not receiver_number:
            raise ValueError("Twilio SMS credentials or receiver number is missing.")
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = (account_sid, auth_token)
        
        body = (
            f"ALERT ({severity.upper()})\n"
            f"Alert ID: {alert_id}\n"
            f"Target: {target_user_id or 'N/A'}\n"
            f"Msg: {message}"
        )
        
        payload = {
            "From": from_number,
            "To": receiver_number,
            "Body": body
        }
        
        response = requests.post(url, data=payload, auth=auth, timeout=8)
        if response.status_code not in [200, 201]:
            raise RuntimeError(f"Twilio API returned status {response.status_code}: {response.text}")

    def _dispatch_zalo(self, oa_token: str, receiver_id: str, event_id: str, alert_id: str, severity: str, message: str, target_user_id: Optional[str]):
        if not oa_token or not receiver_id:
            raise ValueError("Zalo OA Token or Receiver ID is missing.")
            
        url = "https://openapi.zalo.me/v3.0/oa/message/cs"
        headers = {
            "access_token": oa_token,
            "Content-Type": "application/json"
        }
        
        text_msg = (
            f"🚨 Báo động ({severity.upper()})\n"
            f"Mã cảnh báo: {alert_id}\n"
            f"Người nhận: {target_user_id or 'N/A'}\n"
            f"Thời gian: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"---\n{message}"
        )
        
        payload = {
            "recipient": {
                "user_id": receiver_id
            },
            "message": {
                "text": text_msg
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code != 200:
            raise RuntimeError(f"Zalo API returned status {response.status_code}: {response.text}")
            
        data = response.json()
        if data.get("error") != 0:
            raise RuntimeError(f"Zalo API Error: {data.get('message')}")

# Instance toàn cục điều khiển toàn bộ logic thông báo
notification_engine = NotificationEngine()
