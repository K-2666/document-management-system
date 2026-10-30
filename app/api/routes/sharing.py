
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit_logging import log_audit
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.document_share import DocumentShare
from app.models.user import User
from app.schemas.document_share import (
    DocumentShareCreate,
    DocumentShareResponse,
    SharedDocumentListResponse,
    SharedDocumentResponse,
)
from app.services.document_service import UPLOAD_DIR


router = APIRouter(prefix="/sharing", tags=["Document Sharing"])


def get_owned_document(
    document_id: int,
    current_user: User,
    db: Session,
) -> Document:
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot manage document sharing",
        )

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or an administrator can manage sharing",
        )

    return document


@router.post(
    "/{document_id}",
    response_model=DocumentShareResponse,
    status_code=status.HTTP_201_CREATED,
)
def share_document(
    document_id: int,
    share_data: DocumentShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_owned_document(document_id, current_user, db)

    recipient = db.scalar(
        select(User).where(
            func.lower(User.username) == share_data.username.lower()
        )
    )

    if recipient is None or not recipient.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )

    if recipient.id == document.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot share a document with its owner",
        )

    existing_share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document.id,
            DocumentShare.shared_with_user_id == recipient.id,
        )
    )

    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already shared with this user",
        )

    share = DocumentShare(
        document_id=document.id,
        shared_with_user_id=recipient.id,
        shared_by_user_id=current_user.id,
        permission=share_data.permission,
    )

    db.add(share)

    try:
        db.commit()
        db.refresh(share)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already shared with this user",
        ) from None

    log_audit(
        action="DOCUMENT_SHARED",
        user_id=current_user.id,
        target_id=document.id,
        details={
            "recipient_user_id": recipient.id,
            "permission": share.permission,
        },
    )

    return share


@router.get("/received/list", response_model=SharedDocumentListResponse)
def list_shared_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Document, DocumentShare.permission)
        .join(
            DocumentShare,
            DocumentShare.document_id == Document.id,
        )
        .where(
            DocumentShare.shared_with_user_id == current_user.id,
            Document.owner_id != current_user.id,
        )
    )

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    rows = db.execute(
        query.order_by(DocumentShare.created_at.desc(), Document.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    items = [
        SharedDocumentResponse(
            id=document.id,
            owner_id=document.owner_id,
            original_filename=document.original_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            created_at=document.created_at,
            permission=permission,
        )
        for document, permission in rows
    ]

    return SharedDocumentListResponse(
        items=items,
        total=total,
    )


@router.get(
    "/{document_id}/download",
    name="download_shared_document",
)
def download_shared_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id:
        share = db.scalar(
            select(DocumentShare).where(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_user_id == current_user.id,
            )
        )

        if share is None:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sharing permission found for this document",
        )
        if share.permission not in {"viewer", "editor"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid document sharing permission",
            )

    file_path = (UPLOAD_DIR / document.stored_filename).resolve()

    if file_path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file does not exist",
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


@router.delete("/{document_id}/{recipient_id}", status_code=204)
def revoke_document_share(
    document_id: int,
    recipient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to revoke this share",
        )

    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == recipient_id,
        )
    )

    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document share not found",
        )

    db.delete(share)
    db.commit()

    log_audit(
        action="DOCUMENT_SHARE_REVOKED",
        user_id=current_user.id,
        target_id=document_id,
        details={"recipient_user_id": recipient_id},
    )
