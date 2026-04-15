from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.endpoints import router as api_router
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(api_router, prefix="/api")

# Serve the built React frontend (for production / HF Spaces)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/")
    def serve_root():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """Catch-all: serve index.html for client-side routing."""
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"status": "Marketing Intelligence API is running"}