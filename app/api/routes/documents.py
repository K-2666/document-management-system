
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit_logging import log_audit
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document_service import UPLOAD_DIR, save_document


router = APIRouter(prefix="/documents", tags=["Documents"])


def get_owned_document(document_id: int, owner_id: int, db: Session) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot upload documents",
        )

    document = save_document(file, current_user.id, db)

    log_audit(
        action="DOCUMENT_UPLOADED",
        user_id=current_user.id,
        target_id=document.id,
        details={"filename": document.original_filename},
    )

    return document


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    filename: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Document).where(Document.owner_id == current_user.id)

    if filename:
        query = query.where(
            Document.original_filename.ilike(f"%{filename}%")
        )

    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    documents = db.scalars(
        query.order_by(Document.created_at.desc(), Document.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return DocumentListResponse(
        items=documents,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_details(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_document(document_id, current_user.id, db)


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_owned_document(document_id, current_user.id, db)
    file_path = (UPLOAD_DIR / document.stored_filename).resolve()

    if file_path.parent != UPLOAD_DIR or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        )

    log_audit(
        action="DOCUMENT_DOWNLOAD_REQUESTED",
        user_id=current_user.id,
        target_id=document.id,
        details={"filename": document.original_filename},
    )

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_owned_document(document_id, current_user.id, db)
    file_path = (UPLOAD_DIR / document.stored_filename).resolve()

    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot delete documents",
        )

    if file_path.parent != UPLOAD_DIR:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid stored file path",
        )

    document_id_for_audit = document.id
    filename_for_audit = document.original_filename

    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise

    log_audit(
        action="DOCUMENT_DELETED",
        user_id=current_user.id,
        target_id=document_id_for_audit,
        details={"filename": filename_for_audit},
    )

    if file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document record deleted, but the stored file could not be removed",
            ) from None
