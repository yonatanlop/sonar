from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.mention import SocialPlatform

router = APIRouter(prefix="/platforms", tags=["Plataformas"])


@router.get("")
def list_platforms(db: Session = Depends(get_db), _=Depends(get_current_user)):
    platforms = db.query(SocialPlatform).filter(SocialPlatform.active == True).all()
    return [{"id": p.id, "name": p.name, "code": p.code} for p in platforms]
