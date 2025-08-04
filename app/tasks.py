"""from app.worker import celery
from app.processor import run_multiple_plugins
from app.ai_verdict import get_ai_verdict  # Import AI analysis module
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "mcp.db")


@celery.task(name="run_multiple_plugins")
def run_plugins(file_path: str, plugin_list: list[str]):
    
    Celery task to run multiple Volatility plugins on a memory image and get AI verdict.
    Returns:
        dict: Plugin results + AI verdict
    
    try:
        results = run_multiple_plugins(file_path, plugin_list)

        # Merge plugin results into one text blob for AI processing
        combined_output = "\n".join([f"--- {p} ---\n{res}" for p, res in results.items()])
        verdict = get_ai_verdict(combined_output)

        # Optionally log verdict or update DB if needed here
        return {
            "results": results,
            "ai_verdict": verdict
        }

    except Exception as e:
        return {
            "error": str(e),
            "ai_verdict": "Unable to process due to error."
        }"""

