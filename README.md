# Secure Document Management System

A secure document management and file-sharing REST API built with FastAPI and MySQL. The application supports user authentication, document uploads, controlled file sharing, role-based access control, and audit logging.

## Features

- User registration and login
- Password hashing using Argon2
- JWT-based authentication
- User profile endpoint
- Document upload, listing, viewing, downloading, and deletion
- Document sharing with other users
- Shared document access and permission revocation
- Role-based access control
- File size, extension, MIME type, and content validation
- Randomized filenames to reduce filename-related security risks
- Request logging and audit logging
- Login rate limiting
- Automated tests using pytest
- Database migrations using Alembic

## Technology Stack

- Python
- FastAPI
- MySQL
- SQLAlchemy
- Alembic
- JWT
- Argon2
- Pydantic
- Pytest

## Project Structure

```text
Document_management_system/
├── alembic/
├── app/
├── tests/
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Prerequisites

Install the following before running the project:

- Python
- MySQL Server
- Git

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/K-2666/document-management-system.git
cd document-management-system
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Database Configuration

1. Start your MySQL server.
2. Create a MySQL database for the application.
3. Configure the database connection and other required settings using the environment variables in `.env.example`.
4. Create your local `.env` file and provide the appropriate values.

Do not commit your `.env` file or database passwords to GitHub.

## Database Migrations

Run the database migrations:

```bash
alembic upgrade head
```

## Running the Application

Start the FastAPI development server using the command configured for your application.

For the standard FastAPI entry point `app.main:app`, use:

```bash
uvicorn app.main:app --reload
```

If your application uses a different entry point, replace `app.main:app` with the correct module and application name.

Once the server starts, open:

- API documentation: `http://127.0.0.1:8000/docs`
- Alternative API documentation: `http://127.0.0.1:8000/redoc`

## Testing

Run the automated tests with:

```bash
pytest
```

## Security

The project implements authentication, password hashing, authorization checks, file validation, randomized filenames, and audit logging.

The application is intended as a learning and development project. Before production deployment, review file storage security, rate limiting, secret management, database permissions, HTTPS configuration, and logging practices.

## Future Improvements

- Cloud-based document storage
- Redis-backed rate limiting
- Docker deployment
- CI/CD integration
- Additional security and integration tests

## Author

Karthikeya
