"""ASGI entry point for the incremental Co-Tour migration."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from cotour.recommendations import (
    Recommendation,
    RecommendationInputError,
    RecommendationQuery,
    RecommendationService,
)


WEB_APP_DIRECTORY = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    country: str = Field(default="Tunisia", min_length=1, max_length=100)
    german_city: str = Field(default="Munich", min_length=1, max_length=100)
    visit_type: str = Field(default="solo", min_length=1, max_length=40)
    accommodation: str = Field(default="Maxvorstadt", min_length=1, max_length=100)
    visit_date: date = date(2020, 8, 10)
    preference: str = Field(default="outdoors", min_length=1, max_length=20)

    def to_query(self) -> RecommendationQuery:
        return RecommendationQuery(**self.model_dump())


class RecommendationResult(BaseModel):
    rank: int
    name: str
    address: str
    score: float


class RecommendationResponse(BaseModel):
    recommendations: tuple[RecommendationResult, ...]


def _serialize(results: tuple[Recommendation, ...]) -> RecommendationResponse:
    return RecommendationResponse(
        recommendations=tuple(
            RecommendationResult(
                rank=result.rank,
                name=result.name,
                address=result.address,
                score=result.score,
            )
            for result in results
        )
    )


def create_app(service: RecommendationService | None = None) -> FastAPI:
    application = FastAPI(
        title="Co-Tour API",
        summary="Data-driven tourism recommendations for Munich",
        version="1.0.0",
    )
    application.state.recommendation_service = service or RecommendationService(
        WEB_APP_DIRECTORY / "data"
    )
    allowed_hosts = [
        host.strip()
        for host in os.environ.get(
            "FASTAPI_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver"
        ).split(",")
        if host.strip()
    ]
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    application.mount(
        "/static",
        StaticFiles(directory=WEB_APP_DIRECTORY / "webapp" / "static"),
        name="static",
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://unpkg.com; "
            "style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; object-src 'none'"
        )
        return response

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={"title": "Home"},
        )

    def render_recommendations(
        request: Request,
        form: RecommendationRequest,
        *,
        fragment: bool = False,
    ):
        recommendation_service = request.app.state.recommendation_service
        try:
            results = recommendation_service.recommend(form.to_query())
            error = None
            status_code = 200
        except RecommendationInputError as exc:
            results = ()
            error = str(exc)
            status_code = 422
        context = {
            "form": form,
            "options": recommendation_service.options(),
            "recommendations": results,
            "error": error,
            "title": "Recommendations",
        }
        return templates.TemplateResponse(
            request=request,
            name="recommendation_results.html" if fragment else "recommendations.html",
            context=context,
            status_code=status_code,
        )

    @application.get(
        "/tourism_recommendation_system/",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def recommendation_page(request: Request):
        return render_recommendations(request, RecommendationRequest())

    @application.post(
        "/tourism_recommendation_system/",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def submit_recommendation_form(
        request: Request,
        form: Annotated[RecommendationRequest, Form()],
    ):
        return render_recommendations(
            request, form, fragment=request.headers.get("HX-Request") == "true"
        )

    @application.post(
        "/api/v1/recommendations",
        response_model=RecommendationResponse,
        tags=["recommendations"],
    )
    def recommendation_api(
        request: Request, payload: RecommendationRequest
    ) -> RecommendationResponse:
        try:
            results = request.app.state.recommendation_service.recommend(
                payload.to_query()
            )
        except RecommendationInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _serialize(results)

    return application


app = create_app()
