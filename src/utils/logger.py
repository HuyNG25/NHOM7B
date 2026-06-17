import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Đảm bảo thư mục lưu log tồn tại
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "evidence", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "notification_service.log")

    # Tạo logger chính
    logger = logging.getLogger("NotificationService")
    logger.setLevel(logging.INFO)

    # Tránh lặp handler nếu hàm được gọi nhiều lần
    if logger.handlers:
        return logger

    # Định dạng log cho Console (màu sắc và dễ đọc)
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Định dạng log cho File (JSON-like hoặc chi tiết đầy đủ để làm đầu vào cho Analytics Service)
    file_formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": %(message)s}',
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File Handler (Ghi log xoay vòng tối đa 5MB/file, giữ lại 3 file cũ)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    return logger

# Tạo logger instance toàn cục để dùng chung
app_logger = setup_logger()
