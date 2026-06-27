"""
File upload and download endpoints.
Uses storage utility — works with local, MinIO, or S3.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.proposal import ProposalDocument
from app.models.user import User
from app.dependencies import get_current_user
from app.config import settings
from app.utils.storage import storage

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/proposals/{proposal_id}/documents",
             summary="Upload a document for a proposal")
async def upload_document(
    proposal_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            400,
            f"File type '{file.content_type}' not allowed. Only PDF and DOCX accepted."
        )

    # Read and validate size
    file_bytes = await file.read()
    file_size  = len(file_bytes)

    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            400,
            f"File size {file_size / 1024 / 1024:.1f}MB exceeds "
            f"{settings.max_file_size_mb}MB limit."
        )

    # Upload to storage
    storage_key = storage.upload(file_bytes, file.filename, file.content_type)

    # Save metadata to DB
    doc = ProposalDocument(
        proposal_id = proposal_id,
        file_name   = file.filename,
        file_type   = file.content_type,
        file_size   = file_size,
        storage_key = storage_key,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return ok(
        data={
            "id":        str(doc.id),
            "file_name": doc.file_name,
            "file_size": doc.file_size,
            "file_type": doc.file_type,
        },
        message="Document uploaded successfully."
    )


@router.get("/documents/{doc_id}/download",
            summary="Get signed download URL for a document")
def get_download_url(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(ProposalDocument).filter(
        ProposalDocument.id == doc_id,
        ProposalDocument.deleted_at.is_(None),
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found.")

    signed_url = storage.get_signed_url(
        doc.storage_key,
        expires_in=settings.signed_url_expire_seconds,
    )

    return ok(data={
        "download_url": signed_url,
        "file_name":    doc.file_name,
        "file_size":    doc.file_size,
        "expires_in":   settings.signed_url_expire_seconds,
    })


@router.get("/documents/{doc_id}/content",
            summary="Stream document content (local storage only)")
def get_document_content(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    For local dev storage — streams the file directly.
    In production (S3/MinIO), use the signed URL instead.
    """
    if settings.storage_provider != "local":
        raise HTTPException(
            400,
            "Direct content streaming only available for local storage. "
            "Use /download for signed URL."
        )

    doc = db.query(ProposalDocument).filter(
        ProposalDocument.id == doc_id,
        ProposalDocument.deleted_at.is_(None),
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found.")

    file_bytes = storage.get_file(doc.storage_key)
    if not file_bytes:
        raise HTTPException(404, "File not found in storage.")

    return Response(
        content      = file_bytes,
        media_type   = doc.file_type,
        headers      = {
            "Content-Disposition": f'attachment; filename="{doc.file_name}"'
        },
    )


@router.get("/proposals/{proposal_id}/documents",
            summary="List documents for a proposal")
def list_documents(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    docs = db.query(ProposalDocument).filter(
        ProposalDocument.proposal_id == proposal_id,
        ProposalDocument.deleted_at.is_(None),
        ProposalDocument.is_active   == True,
    ).all()
    return ok(data=[
        {
            "id":        str(d.id),
            "file_name": d.file_name,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "version":   d.version_no,
        }
        for d in docs
    ])


@router.delete("/documents/{doc_id}",
               summary="Delete a document")
def delete_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(ProposalDocument).filter(
        ProposalDocument.id == doc_id,
        ProposalDocument.deleted_at.is_(None),
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found.")

    # Delete from storage
    storage.delete(doc.storage_key)

    # Soft delete from DB
    doc.soft_delete()
    db.commit()

    return ok(message="Document deleted.")