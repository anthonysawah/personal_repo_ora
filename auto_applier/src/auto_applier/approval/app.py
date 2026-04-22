from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from ..db import session_scope
from ..models import Application, AppStatus, Job
from ..tailor.tailor import TailoredResume

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(title="auto_applier")


def _snippet(text: str, n: int = 240) -> str:
    t = " ".join((text or "").split())
    return t[:n] + ("…" if len(t) > n else "")


@app.get("/", response_class=HTMLResponse)
def queue(request: Request):
    with session_scope() as session:
        apps = session.exec(
            select(Application).where(Application.status == AppStatus.pending_approval)
        ).all()
        apps = sorted(apps, key=lambda a: a.fit_score or 0, reverse=True)
        rows = []
        for a in apps:
            job = session.get(Job, a.job_id)
            if job:
                rows.append({"app": a, "job": job, "snippet": _snippet(job.jd_text)})
    return templates.TemplateResponse(request, "queue.html", {"apps": rows})


@app.get("/app/{app_id}", response_class=HTMLResponse)
def detail(request: Request, app_id: int):
    with session_scope() as session:
        a = session.get(Application, app_id)
        if not a:
            raise HTTPException(404)
        job = session.get(Job, a.job_id)
        tailored: Optional[TailoredResume] = None
        if a.tailored_resume_json:
            try:
                tailored = TailoredResume.model_validate(json.loads(a.tailored_resume_json))
            except Exception:
                tailored = None
    return templates.TemplateResponse(
        request, "detail.html", {"app": a, "job": job, "tailored": tailored}
    )


@app.get("/app/{app_id}/pdf")
def get_pdf(app_id: int):
    with session_scope() as session:
        a = session.get(Application, app_id)
        if not a or not a.resume_pdf_path:
            raise HTTPException(404)
        path = Path(a.resume_pdf_path)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(str(path), media_type="application/pdf")


@app.get("/app/{app_id}/docx")
def get_docx(app_id: int):
    with session_scope() as session:
        a = session.get(Application, app_id)
        if not a or not a.resume_docx_path:
            raise HTTPException(404)
        path = Path(a.resume_docx_path)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@app.post("/app/{app_id}/approve")
def approve(app_id: int):
    with session_scope() as session:
        a = session.get(Application, app_id)
        if not a:
            raise HTTPException(404)
        a.status = AppStatus.approved
        session.add(a)
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/app/{app_id}/skip")
def skip(app_id: int):
    with session_scope() as session:
        a = session.get(Application, app_id)
        if not a:
            raise HTTPException(404)
        a.status = AppStatus.skipped
        session.add(a)
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/bulk")
async def bulk(request: Request):
    form = await request.form()
    action = form.get("action")
    ids = form.getlist("app_ids")
    if not ids:
        return RedirectResponse("/", status_code=303)
    new_status = AppStatus.approved if action == "approve" else AppStatus.skipped
    with session_scope() as session:
        for sid in ids:
            a = session.get(Application, int(sid))
            if a:
                a.status = new_status
                session.add(a)
        session.commit()
    return RedirectResponse("/", status_code=303)


def serve(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    from .. import config as _config

    uvicorn.run(
        "auto_applier.approval.app:app",
        host=host or _config.settings.approval_host,
        port=port or _config.settings.approval_port,
        reload=False,
        log_level="info",
    )
