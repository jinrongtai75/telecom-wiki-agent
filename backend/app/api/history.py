import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import ChatHistory, Feedback, User
from app.models.schemas import FeedbackRequest, HistoryItem, SourceInfo
from app.security.auth_deps import get_current_user

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryItem])
def get_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        sources = [SourceInfo(**s) for s in json.loads(row.sources)]
        result.append(
            HistoryItem(
                id=row.id,
                question=row.question,
                answer=row.answer,
                sources=sources,
                provider=row.provider,
                created_at=row.created_at,
            )
        )
    return result


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(ChatHistory)
        .filter(ChatHistory.id == history_id, ChatHistory.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).delete()
    db.commit()


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history = db.query(ChatHistory).filter(
        ChatHistory.id == req.history_id,
        ChatHistory.user_id == current_user.id,
    ).first()
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History not found")

    feedback = Feedback(history_id=req.history_id, rating=req.rating)
    db.add(feedback)
    db.commit()
    return {"status": "ok"}
