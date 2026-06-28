# Hướng dẫn chạy Local - Notification Service

Tài liệu này hướng dẫn cách cài đặt và chạy thử nghiệm Notification Service trong môi trường local (Windows).

---

## Yêu cầu hệ thống
* Python 3.9 trở lên
* Trình duyệt web hiện đại (Chrome, Edge, Firefox, Safari)

## Cách chạy từng bước

### 1. Tạo môi trường ảo (Virtual Environment)
Mở terminal (PowerShell hoặc Command Prompt) tại thư mục `Notify_app` và chạy lệnh sau:
```powershell
python -m venv venv
```

### 2. Kích hoạt môi trường ảo
* **PowerShell**:
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
* **Command Prompt (cmd)**:
  ```cmd
  .\venv\Scripts\activate.bat
  ```

### 3. Cài đặt các thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### 4. Thiết lập file cấu hình môi trường
File `.env` đã được tạo sẵn cấu hình chế độ **Mock (chế độ mô phỏng)** cho tất cả các kênh thông báo:
```env
MOCK_TELEGRAM=true
MOCK_DISCORD=true
MOCK_EMAIL=true
MOCK_SMS=true
MOCK_ZALO=true
```
Nếu bạn muốn thử gửi qua các kênh thật (Telegram Bot thật, Discord Webhook thật, SMTP Email thật), hãy sửa giá trị thành `false` và điền thông tin xác thực tương ứng trong file `.env`.

### 5. Chạy ứng dụng
Khởi động server bằng lệnh:
```bash
python src/main.py
```

Khi server khởi chạy thành công, màn hình sẽ hiển thị:
```text
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 6. Truy cập Dashboard kiểm thử
Mở trình duyệt và truy cập:
* **Dashboard chính**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **API Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
