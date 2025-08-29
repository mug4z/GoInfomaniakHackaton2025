# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Ensure ./common is on the Python path for local runs
PROJECT_ROOT = Path(__file__).resolve().parent
COMMON_DIR = str(PROJECT_ROOT / "common")
if COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

import typer

app = typer.Typer()


@app.command()
def fastapi():
    """Run FastAPI server."""
    import uvicorn

    uvicorn.run(
            "api.main:app",
            host="127.0.0.1",
            port=8000,
            log_level="debug",
            log_config="./logging.yaml",
            reload_dirs=["./api", "./common"],  # Add all relevant dirs
            reload=True,
            )


if __name__ == "__main__":
    app()
