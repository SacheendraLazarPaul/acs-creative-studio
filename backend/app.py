"""
AI Creative Studio v3 — thin entry point.
All logic lives in: config.py, models.py, search.py, chat.py,
                    downloads.py, generation.py, routes.py
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from config import STATIC_DIR, OUTPUT_DIR, BASE_DIR
from routes import router

app = FastAPI(title="AI Creative Studio v3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(router)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

assets_dir = STATIC_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    now = datetime.now()
    print(f"\n AI Creative Studio v3")
    print(f" {now.strftime('%A, %B %d, %Y')} {now.strftime('%I:%M %p')}")
    print(f" Dir:  {BASE_DIR}")
    print(f" Open: http://localhost:7860\n")
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
