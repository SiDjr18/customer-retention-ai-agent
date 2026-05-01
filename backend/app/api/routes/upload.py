"""
Universal file upload endpoint.

POST /upload/data
  Accepts: .csv, .xlsx, .xls, .txt, .pdf
  Returns: file_id, profile, domain inference, warnings
"""
from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.data_engine.universal_data_service import (
    EXTENSION_MAP,
    process_upload,
    set_active_file_path,
)

router = APIRouter()

# uploads/ directory lives next to backend/
_UPLOADS_DIR = os.path.join(
    os.path.dirname(__file__),          # routes/
    "..", "..", "..", "uploads",        # → backend/uploads/
)
_UPLOADS_DIR = os.path.normpath(_UPLOADS_DIR)

_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB hard cap

_ALLOWED_EXTENSIONS = set(EXTENSION_MAP.keys())  # .csv .xlsx .xls .txt .pdf


@router.post(
    "/data",
    summary="Upload a data file (CSV / Excel / TXT / PDF) for profiling and domain inference",
    response_class=JSONResponse,
)
async def upload_data(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload any of: .csv, .xlsx, .xls, .txt, .pdf

    Returns a structured response containing:
    - file_id, filename, file_type
    - rows, columns
    - profile_summary (stats, missing values, duplicates, sample rows)
    - inference (detected domain, use cases, key metrics, recommended analysis)
    - warnings (large file sampling notices, parse errors, etc.)
    """
    os.makedirs(_UPLOADS_DIR, exist_ok=True)

    # Extension check
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    # Stream to a temp file so we can measure size before processing
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext,
            dir=_UPLOADS_DIR,
        ) as tmp:
            tmp_path = tmp.name
            total    = 0
            chunk_sz = 1024 * 1024   # 1 MB chunks
            while True:
                chunk = await file.read(chunk_sz)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_FILE_SIZE:
                    os.unlink(tmp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds 2 GB limit ({total / 1024**3:.2f} GB received so far).",
                    )
                tmp.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}")

    # Process
    try:
        result = process_upload(
            file_path=tmp_path,
            original_filename=filename,
            content_type=file.content_type or "",
            file_size=total,
            uploads_dir=_UPLOADS_DIR,
        )
    except Exception as exc:
        # Clean up temp file on processing error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")

    # Rename temp file to uploads/<file_id><ext> for persistence
    dest = os.path.join(_UPLOADS_DIR, f"{result['file_id']}{ext}")
    try:
        shutil.move(tmp_path, dest)
        # Register final path so DatasetService and agents can use it
        if result.get("file_type") in ("csv", "xls", "xlsx"):
            set_active_file_path(dest)
    except OSError:
        pass   # keep temp file if move fails — not fatal

    return JSONResponse(content=result)
