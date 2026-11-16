from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import hash_password, RoleDependency
from ..database import get_db
from ..models import User
from ..schemas import PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = ("supervisor", "duty", "maintenance")


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="无效的用户角色")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        real_name=body.real_name,
        role=body.role,
        is_active=body.is_active if body.is_active is not None else True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/{user_id}/reset_password", response_model=UserOut)
def reset_password(
    user_id: int,
    body: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="无效的用户角色")
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data.pop("password"))
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)