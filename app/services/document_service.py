
from pathlib import Path
from uuid import uuid4
import zipfile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document


UPLOAD_DIR = Path("uploads").resolve()
MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".txt": {"text/plain"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
}


def validate_file_content(path: Path, extension: str) -> bool:
    with path.open("rb") as file:
        header = file.read(16)

    if extension == ".pdf":
        return header.startswith(b"%PDF-")

    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")

    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")

    if extension == ".txt":
        try:
            with path.open("r", encoding="utf-8") as file:
                for chunk in iter(lambda: file.read(8192), ""):
                    if "\x00" in chunk:
                        return False
            return True
        except UnicodeDecodeError:
            return False

    if extension == ".docx":
        if not zipfile.is_zipfile(path):
            return False

        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                return (
                    "[Content_Types].xml" in names
                    and "word/document.xml" in names
                )
        except (OSError, zipfile.BadZipFile):
            return False

    return False


def save_document(file: UploadFile, owner_id: int, db: Session) -> Document:
    original_filename = Path(file.filename or "").name

    if not original_filename or original_filename in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid filename is required",
        )

    extension = Path(original_filename).suffix.lower()
    allowed_mime_types = ALLOWED_TYPES.get(extension)

    if not allowed_mime_types or file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="This file type is not supported",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}{extension}"
    destination = UPLOAD_DIR / stored_filename
    size = 0

    try:
        with destination.open("xb") as output:
            while True:
                chunk = file.file.read(CHUNK_SIZE)

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Maximum file size is 10 MB",
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty files are not allowed",
            )

        if not validate_file_content(destination, extension):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File contents do not match the declared file type",
            )

        document = Document(
            owner_id=owner_id,
            original_filename=original_filename[:255],
            stored_filename=stored_filename,
            content_type=file.content_type,
            size_bytes=size,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except Exception:
        db.rollback()

        if destination.exists():
            destination.unlink()

        raise
    finally:
        file.file.close()
