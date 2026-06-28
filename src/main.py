import uvicorn
import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

# Thêm thư mục gốc vào PYTHONPATH để tránh lỗi ModuleNotFoundError khi chạy trực tiếp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load biến môi trường từ .env trước khi import routes
load_dotenv(override=True)


from src.routes.alerts import router as alerts_router, ProblemException
from src.routes.channels import router as channels_router
from src.routes.analytics import router as analytics_router
from src.utils.logger import app_logger

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="Notification Service",
    description="Dịch vụ gửi thông báo sự kiện bất thường hệ thống (FIT4110)",
    version="1.0.0"
)

@app.on_event("startup")
def startup_event():
    from src.utils.database import db_manager
    db_manager.initialize_pool()


# Exception Handler cho lỗi xác thực Bearer/Logic nghiệp vụ (Problem Details JSON)
@app.exception_handler(ProblemException)
async def problem_exception_handler(request: Request, exc: ProblemException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content,
        media_type="application/problem+json"
    )

# Exception Handler cho lỗi Schema / Validation đầu vào từ Pydantic (Trả về 400 Bad Request)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Trích xuất lỗi chi tiết
    errors = exc.errors()
    error_detail = "Dữ liệu payload sai định dạng JSON Schema cấu trúc đầu vào"
    if errors:
        loc = " -> ".join([str(x) for x in errors[0].get("loc", [])])
        msg = errors[0].get("msg", "Sai cấu trúc")
        error_detail = f"Lỗi trường [{loc}]: {msg}"

    return JSONResponse(
        status_code=400,
        content={
            "type": "https://campus.local/errors/validation",
            "title": "Dữ liệu không hợp lệ",
            "status": 400,
            "detail": error_detail,
            "instance": request.url.path
        },
        media_type="application/problem+json"
    )

# Cấu hình CORS cho phép Dashboard kết nối API từ các port khác nhau khi kiểm thử local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Đăng ký các router API
app.include_router(alerts_router)
app.include_router(channels_router)
app.include_router(analytics_router)  # Endpoint hứng dữ liệu từ B6

# Mount thư mục tĩnh để phục vụ giao diện Dashboard
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/", include_in_schema=False)
    def read_root():
        """
        Trả về giao diện trang chủ Dashboard kiểm thử.
        """
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    app_logger.warning("Static directory not found at src/static. Front-end will not be served.")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    log_level = os.getenv("LOG_LEVEL", "info")
    
    app_logger.info(f"Starting server on http://{host}:{port}")
    uvicorn.run("src.main:app", host=host, port=port, log_level=log_level, reload=True)
