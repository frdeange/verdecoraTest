from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import UploadWebSettings, get_settings
from .middleware.session_security import SessionSecurityMiddleware, security_template_context
from .routes import router

BASE_DIR = Path(__file__).resolve().parent


def create_app(settings: UploadWebSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    app = FastAPI(title="Verdecora Upload Web")
    app.state.settings = resolved_settings
    app.add_middleware(SessionSecurityMiddleware, settings=resolved_settings)
    app.state.templates = Jinja2Templates(
        directory=str(BASE_DIR / "templates"),
        context_processors=[security_template_context],
    )
    app.state.templates.env.globals.update(app_name="Verdecora Upload Web", current_year=datetime.now(UTC).year)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("src.upload_web.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
