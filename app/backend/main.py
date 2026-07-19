from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import AuthenticatedUser, get_current_user
from drafts import router as drafts_router
from email_generation import router as email_generation_router
from gmail import router as gmail_router
from processing_queues import router as processing_queues_router
from resumes import router as resumes_router

load_dotenv()

app = FastAPI(title="AI Email Agent API")
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resumes_router)
app.include_router(email_generation_router)
app.include_router(drafts_router)
app.include_router(gmail_router)
app.include_router(processing_queues_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/v1/auth/me")
def authenticated_user(user: CurrentUser) -> AuthenticatedUser:
    return user
