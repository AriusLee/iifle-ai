from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.config import settings
from app.models.user import User

router = APIRouter()


class UpdateApiKeyRequest(BaseModel):
    provider: str = "groq"
    api_key: str


class ApiKeyStatusResponse(BaseModel):
    ai_provider: str
    groq_configured: bool
    groq_key_hint: str | None = None


def _mask_key(key: str) -> str | None:
    if not key or len(key) < 15:
        return None
    return key[:7] + "···" + key[-4:]


@router.get("/api-keys", response_model=ApiKeyStatusResponse)
async def get_api_key_status(current_user: User = Depends(get_current_user)):
    return ApiKeyStatusResponse(
        ai_provider=settings.AI_PROVIDER,
        groq_configured=bool(settings.GROQ_API_KEY),
        groq_key_hint=_mask_key(settings.GROQ_API_KEY),
    )


@router.put("/api-keys")
async def update_api_keys(
    data: UpdateApiKeyRequest,
    current_user: User = Depends(get_current_user),
):
    settings.GROQ_API_KEY = data.api_key
    settings.AI_PROVIDER = "groq"
    _update_env_file("GROQ_API_KEY", data.api_key)
    return {"status": "ok", "provider": "groq", "configured": bool(data.api_key)}


def _update_env_file(key: str, value: str):
    import pathlib
    env_path = pathlib.Path(__file__).resolve().parents[3] / ".env"
    lines = []
    found = False

    if env_path.exists():
        lines = env_path.read_text().splitlines()

    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")
