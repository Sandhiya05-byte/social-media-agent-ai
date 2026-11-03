from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.creator import Creator
from app.schemas.creator import CreatorCreate, CreatorRead

router = APIRouter(prefix="/api/creators", tags=["creators"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=CreatorRead, status_code=status.HTTP_201_CREATED)
def create_creator(payload: CreatorCreate, db: Session = Depends(get_db)):
    existing = db.query(Creator).filter(Creator.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Creator with this email already exists.")

    creator = Creator(
        name=payload.name,
        brand_name=payload.brand_name,
        niche=payload.niche,
        email=payload.email,
        platform_focus=payload.platform_focus,
        bio=payload.bio,
        website=payload.website,
        approved_for_publication=payload.approved_for_publication,
        authorized_for_avatar_use=payload.authorized_for_avatar_use,
    )
    db.add(creator)
    db.commit()
    db.refresh(creator)
    return creator


@router.get("/{creator_id}", response_model=CreatorRead)
def get_creator(creator_id: int, db: Session = Depends(get_db)):
    creator = db.query(Creator).filter(Creator.id == creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found.")
    return creator


@router.get("", response_model=list[CreatorRead])
def list_creators(db: Session = Depends(get_db)):
    return db.query(Creator).order_by(Creator.created_at.desc()).all()
