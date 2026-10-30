
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models import Document, DocumentShare, User


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    app.state.TestingSessionLocal = TestingSessionLocal

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    import app.api.routes.documents as document_routes
    import app.api.routes.sharing as sharing_routes
    import app.services.document_service as document_service

    monkeypatch.setattr(document_routes, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(sharing_routes, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(document_service, "UPLOAD_DIR", tmp_path)

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
