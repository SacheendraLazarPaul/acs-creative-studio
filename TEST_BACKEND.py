"""Run this with: C:\Python312\python.exe TEST_BACKEND.py"""
import sys, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
sys.path.insert(0, ".")

print("Testing app.py imports...")
print(f"Working dir: {os.getcwd()}")
print(f"Python: {sys.executable}")
print()

try:
    from fastapi import FastAPI
    print("[OK] fastapi")
except Exception as e:
    print(f"[FAIL] fastapi: {e}"); sys.exit(1)

try:
    from fastapi.staticfiles import StaticFiles
    print("[OK] fastapi.staticfiles")
except Exception as e:
    print(f"[FAIL] fastapi.staticfiles: {e}"); sys.exit(1)

try:
    import uvicorn
    print("[OK] uvicorn")
except Exception as e:
    print(f"[FAIL] uvicorn: {e}"); sys.exit(1)

try:
    from pydantic import BaseModel
    print("[OK] pydantic")
except Exception as e:
    print(f"[FAIL] pydantic: {e}"); sys.exit(1)

try:
    import requests
    print("[OK] requests")
except Exception as e:
    print(f"[FAIL] requests: {e}"); sys.exit(1)

print()
print("Now loading full app.py...")
try:
    import app
    print("[OK] app.py loaded cleanly!")
    print()
    print("Starting server at http://localhost:7860 ...")
    import uvicorn
    uvicorn.run(app.app, host="0.0.0.0", port=7860, log_level="info")
except Exception as e:
    import traceback
    print()
    print("=" * 50)
    print(f"ERROR in app.py:")
    print("=" * 50)
    traceback.print_exc()
    print("=" * 50)

input("\nPress Enter to close...")
