from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from detector import DriverMonitor
import logging
import asyncio
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

monitor = DriverMonitor(camera_index=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    monitor.start()
    logger.info("🚀 AlertEye Backend Started")
    yield
    # Shutdown
    monitor.stop()
    logger.info("👋AlertEye  Backend Stopped")

app = FastAPI(title="AlertEye Backend", version="2.0 - Alerts Only", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/alerts")
async def alerts():
    """Lightweight endpoint - returns only alert data (non-blocking)"""
    start_time = time.time()
    alert_data = monitor.get_alerts()
    
    # Log when alerts are active (for debugging)
    active_alerts = [k for k, v in alert_data.items() if isinstance(v, bool) and v]
    if active_alerts:
        logger.debug(f"🚨 Active alerts: {', '.join(active_alerts)}")
    
    # Log slow requests (should be <1ms)
    elapsed = (time.time() - start_time) * 1000
    if elapsed > 5:
        logger.warning(f"⚠️ Slow /alerts request: {elapsed:.2f}ms")
    
    return JSONResponse(alert_data)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "real-time",
        "version": "2.0",
        "description": "Alerts only - camera handled by client"
    }

@app.get("/mjpeg")
async def mjpeg(request: Request):
    """MJPEG streaming with disconnect detection"""

    async def generate():
        for frame in monitor.mjpeg_generator():
            if await request.is_disconnected():
                logger.info("Client disconnected from MJPEG stream")
                break
            yield frame

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0, no-transform",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting SafeDriveVision backend (alerts only)")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")