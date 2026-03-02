from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db import get_db
from .models import Report

router = APIRouter(prefix="/v1/reports", tags=["reports"])


class ReportCreate(BaseModel):
    reporter_id: str
    reported_user_id: str
    reason: str
    message: Optional[str] = None


@router.post("/")
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    report = Report(
        reporter_id=payload.reporter_id,
        reported_user_id=payload.reported_user_id,
        reason=payload.reason,
        message=payload.message,
    )
    db.add(report)
    db.commit()
    return {"success": True}

@router.get("/admin/list")
def list_reports(db: Session = Depends(get_db)):
    return db.query(Report).order_by(Report.created_at.desc()).all()


@router.post("/admin/resolve/{report_id}")
def resolve_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return {"error": "Not found"}
    report.status = "resolved"
    db.commit()
    return {"success": True}
