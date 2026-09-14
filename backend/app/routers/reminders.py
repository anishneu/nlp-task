from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import clock, crud
from app.database import get_db
from app.schemas import TaskOut

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/due", response_model=list[TaskOut])
def due_reminders(db: Session = Depends(get_db)):
    return crud.list_due_tasks(db, clock.now())
