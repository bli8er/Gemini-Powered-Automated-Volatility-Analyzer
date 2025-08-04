import os
import time
import sqlite3
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, start_http_server
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from celery import Celery
from app.gemini_analyzer import analyze_with_gemini # Import the new function

# Base directory (assumes main.py is in /app/app inside container)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define persistent volume paths
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "mcp.db")

# Create directories if missing
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Init FastAPI
app = FastAPI()
Instrumentator().instrument(app).expose(app)

# Static and template folders
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# SQLite Initialization
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            plugin TEXT,
            image TEXT,
            result_path TEXT,
            status TEXT,
            gemini_analysis TEXT, -- Added for Gemini results
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

init_db()

# Prometheus metrics exporter
start_http_server(8001)

# Celery - Fixed Redis connection
celery_app = Celery("worker", broker="redis://redis:6379/0", backend="redis://redis:6379/0")

# Configure Celery
celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Prometheus metrics
plugin_run_counter = Counter("vol_plugin_runs", "Number of plugin runs", ["plugin"])
plugin_error_counter = Counter("vol_plugin_errors", "Number of plugin failures", ["plugin"])
plugin_duration_hist = Histogram("vol_plugin_duration_seconds", "Execution time of plugin", ["plugin"])
image_upload_counter = Counter("vol_image_uploads", "Number of memory image uploads")
celery_task_counter = Counter("vol_celery_tasks_total", "Celery tasks triggered", ["task_name"])
celery_duration_hist = Histogram("vol_celery_duration_seconds", "Celery task duration", ["task_name"])

def update_db(task_id, status, result_path=None, gemini_result=None):
    """Update database with task status and optional Gemini result"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE analysis SET status = ?, result_path = ?, gemini_analysis = ? WHERE task_id = ?", (status, result_path, gemini_result, task_id))

def save_to_db(task_id, plugin, image):
    """Save new task to database"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO analysis (task_id, plugin, image, status) VALUES (?, ?, ?, ?)", (task_id, plugin, image, "PENDING"))

@celery_app.task(name="run_plugin_analysis", bind=True)
def analyze_memory(self, image_path: str, plugin: str) -> str:
    """Celery task to analyze memory dump with volatility plugin"""
    start_time = time.time()
    celery_task_counter.labels(task_name="analyze_memory").inc()
    
    task_id = self.request.id
    result_file = os.path.join(OUTPUT_DIR, f"{plugin}_{os.path.basename(image_path)}.txt")
    
    try:
        update_db(task_id, "STARTED")
        
        cmd = f"python3 ../volatility3/vol.py -f {image_path} {plugin} > {result_file}"
        status = os.system(cmd)
        
        if status != 0:
            plugin_error_counter.labels(plugin=plugin).inc()
            update_db(task_id, "FAILED")
            return f"Plugin '{plugin}' failed with exit code {status}"
        
        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            with open(result_file, 'r') as f:
                plugin_output = f.read()

            gemini_result = analyze_with_gemini(plugin_output, plugin)
            update_db(task_id, "COMPLETED", result_file, gemini_result)
            plugin_run_counter.labels(plugin=plugin).inc()
            return result_file
        else:
            update_db(task_id, "FAILED")
            return f"Plugin '{plugin}' produced no output"
            
    except Exception as e:
        plugin_error_counter.labels(plugin=plugin).inc()
        update_db(task_id, "FAILED")
        return f"Plugin '{plugin}' failed with error: {str(e)}"
    finally:
        duration = time.time() - start_time
        celery_duration_hist.labels(task_name="analyze_memory").observe(duration)

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/analyze/")
async def analyze(plugins: str = Form(...), memory_image: UploadFile = File(...)):
    image_upload_counter.inc()
    image_path = os.path.join(UPLOAD_DIR, memory_image.filename)
    
    with open(image_path, "wb") as f:
        f.write(await memory_image.read())
    
    plugin_list = [p.strip() for p in plugins.split(",") if p.strip()]
    task_ids = []
    
    for plugin in plugin_list:
        plugin_run_counter.labels(plugin=plugin).inc()
        plugin_timer = plugin_duration_hist.labels(plugin=plugin).time()
        
        with plugin_timer:
            async_result = analyze_memory.delay(image_path, plugin)
            save_to_db(async_result.id, plugin, memory_image.filename)
            
            task_ids.append({
                "plugin": plugin,
                "task_id": async_result.id
            })
    
    return JSONResponse({
        "image": memory_image.filename,
        "tasks": task_ids,
        "status": "Processing started"
    })

@app.get("/status/{task_id}")
async def task_status(task_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT status, result_path, gemini_analysis FROM analysis WHERE task_id = ?", (task_id,)).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"task_id": task_id, "status": row[0], "result_path": row[1], "gemini_analysis": row[2]}

@app.get("/download/{task_id}")
async def download_result(task_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT result_path FROM analysis WHERE task_id = ?", (task_id,)).fetchone()
    
    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(status_code=404, detail="Result not found")
    
    return FileResponse(path=row[0], filename=os.path.basename(row[0]), media_type='text/plain')


@app.get("/results/all")
def all_results():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT task_id, plugin, image, status, result_path, gemini_analysis FROM analysis ORDER BY created_at DESC LIMIT 50").fetchall()
    
    return [
        {"task_id": row[0], "plugin": row[1], "image": row[2], "status": row[3], "result_path": row[4], "gemini_analysis": row[5]}
        for row in rows
    ]

@app.get("/results", response_class=HTMLResponse)
def results_page(request: Request):
    return templates.TemplateResponse("results.html", {"request": request})

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
