"""Sequences router — automation sequence UI."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.sequences import SEQUENCES, get_sequence
from mission_control.services.sequence_engine import (
    enroll,
    get_sequence_stats,
    pause_enrollment,
    process_due_sends,
    resume_enrollment,
)

router = APIRouter(prefix="/sequences")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def sequence_list(request: Request):
    """List all sequences with performance summary."""
    sequence_data = []
    for seq_id, seq in SEQUENCES.items():
        stats = get_sequence_stats(seq_id)
        sequence_data.append({
            "definition": seq,
            "stats": stats,
        })

    return templates.TemplateResponse("sequences/index.html", {
        "request": request,
        "active_page": "sequences",
        "sequences": sequence_data,
    })


@router.get("/{sequence_id}")
async def sequence_detail(request: Request, sequence_id: str):
    """Detail view for a sequence — steps, variants, A/B results."""
    seq = get_sequence(sequence_id)
    if not seq:
        return HTMLResponse("<h1>Sequence not found</h1>", status_code=404)

    stats = get_sequence_stats(sequence_id)

    # Get enrollments
    enrollments = db.select(
        "gg_sequence_enrollments",
        match={"sequence_id": sequence_id},
        order="enrolled_at",
        order_desc=True,
        limit=100,
    )

    # Get sends for this sequence's enrollments
    enrollment_ids = [e["id"] for e in enrollments]
    sends = []
    if enrollment_ids:
        all_sends = db.select("gg_sequence_sends", order="sent_at", order_desc=True, limit=500)
        sends = [s for s in all_sends if s["enrollment_id"] in enrollment_ids]

    return templates.TemplateResponse("sequences/detail.html", {
        "request": request,
        "active_page": "sequences",
        "sequence": seq,
        "stats": stats,
        "enrollments": enrollments,
        "sends": sends,
    })


@router.get("/{sequence_id}/enrollments")
async def sequence_enrollments(request: Request, sequence_id: str):
    """Enrollment list for a sequence."""
    seq = get_sequence(sequence_id)
    if not seq:
        return HTMLResponse("<h1>Sequence not found</h1>", status_code=404)

    enrollments = db.select(
        "gg_sequence_enrollments",
        match={"sequence_id": sequence_id},
        order="enrolled_at",
        order_desc=True,
        limit=200,
    )

    return templates.TemplateResponse("sequences/enrollments.html", {
        "request": request,
        "active_page": "sequences",
        "sequence": seq,
        "enrollments": enrollments,
    })


@router.post("/test-enroll")
async def test_enroll(
    request: Request,
    sequence_id: str = Form(...),
    email: str = Form(...),
    name: str = Form("Test Contact"),
):
    """Enroll a test contact in a sequence."""
    result = enroll(email, name, sequence_id, source="test")

    if result:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--success">'
            f'Enrolled {email} in sequence. <a href="/sequences/{sequence_id}">View sequence</a>'
            '</div>'
        )
    else:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--warning">'
            f'Could not enroll {email} — already enrolled or sequence inactive.'
            '</div>'
        )


@router.post("/enrollments/{enrollment_id}/pause")
async def pause(request: Request, enrollment_id: str):
    """Pause an enrollment."""
    success = pause_enrollment(enrollment_id)
    if success:
        return HTMLResponse(
            '<span class="gg-badge mc-status--paused" style="background:var(--gg-color-warm-brown)">paused</span>'
        )
    return HTMLResponse(
        '<span class="gg-badge gg-badge--outline">unchanged</span>'
    )


@router.post("/enrollments/{enrollment_id}/resume")
async def resume(request: Request, enrollment_id: str):
    """Resume a paused enrollment."""
    success = resume_enrollment(enrollment_id)
    if success:
        return HTMLResponse(
            '<span class="gg-badge mc-status--active">active</span>'
        )
    return HTMLResponse(
        '<span class="gg-badge gg-badge--outline">unchanged</span>'
    )


@router.post("/process-now")
async def process_now(request: Request):
    """Manually trigger sequence processing."""
    result = await process_due_sends()
    return HTMLResponse(
        f'<div class="gg-alert gg-alert--success">'
        f'Processed {result["processed"]} enrollments: {result["sent"]} sent, {result["errors"]} errors.'
        f'</div>'
    )
