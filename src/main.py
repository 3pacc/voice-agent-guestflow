from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import logging

from src.api.twilio import router as twilio_router
from src.api.admin.live import router as admin_live_router
from src.db.sql_stock import init_db
from src.db.live_store import init_live_store

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    logger.info("Initializing database...")
    init_db()
    init_live_store()
    logger.info("Database ready.")
    yield


app = FastAPI(
    title="guestFlow-agent",
    description="Realtime Hotel Booking Voice Agent",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include routers
app.include_router(twilio_router, prefix="/twilio", tags=["twilio"])
app.include_router(admin_live_router, prefix="/admin/live", tags=["admin-live"])


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>guestFlow-agent</title>
        </head>
        <body>
            <h1>guestFlow-agent Server Running</h1>
            <p>Ready to receive Twilio WebSocket connections.</p>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
