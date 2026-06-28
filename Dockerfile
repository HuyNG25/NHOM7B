# Sử dụng python base image chính thức làm môi trường chạy
FROM python:3.10-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Đặt biến môi trường ngăn Python tạo file bytecode .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Ngăn Python buffer output (giúp log xuất hiện ngay lập tức)
ENV PYTHONUNBUFFERED=1

# Cài đặt các thư viện cần thiết
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn của dự án vào container
COPY src/ ./src/
COPY docs/ ./docs/
COPY tests/ ./tests/
# Sao chép .env.example làm template (KHÔNG copy .env thật — secrets inject qua docker-compose env_file lúc runtime)
COPY .env.example ./

# Tạo thư mục cho logs
RUN mkdir -p evidence/logs

# Mở cổng 8000 để truy cập bên ngoài
EXPOSE 8000


# Lệnh khởi chạy FastAPI server
CMD ["python", "src/main.py"]
