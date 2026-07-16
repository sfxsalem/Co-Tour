"""FastAPI routes and presentation adapters for tourist-flow analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from cotour.flows import (
    DEFAULT_PLACE,
    DEFAULT_SEASON,
    AttractionCluster,
    FlowDiagnostic,
    FlowInputError,
    FlowQuery,
    FlowResult,
    VisitorOrigin,
)


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
CLUSTER_PALETTE = ("#3c78ff", "#36a269", "#ff9c3b", "#9b72e8")


class AttractionClusterResponse(BaseModel):
    name: str
    latitude: float
    longitude: float
    cluster: int


class VisitorOriginResponse(BaseModel):
    country: str
    share_percent: float
    latitude: float
    longitude: float


class FlowDiagnosticResponse(BaseModel):
    code: str
    message: str
    subject: str


class TouristFlowResponse(BaseModel):
    place: str
    season: str
    attractions: tuple[AttractionClusterResponse, ...]
    origins: tuple[VisitorOriginResponse, ...]
    diagnostics: tuple[FlowDiagnosticResponse, ...]


@dataclass(frozen=True, slots=True)
class SvgMarker:
    label: str
    detail: str
    x: float
    y: float
    radius: float
    fill: str


def serialize_flow(result: FlowResult) -> TouristFlowResponse:
    return TouristFlowResponse(
        place=result.place,
        season=result.season,
        attractions=tuple(
            AttractionClusterResponse(
                name=point.name,
                latitude=point.latitude,
                longitude=point.longitude,
                cluster=point.cluster,
            )
            for point in result.attractions
        ),
        origins=tuple(
            VisitorOriginResponse(
                country=point.country,
                share_percent=point.share_percent,
                latitude=point.latitude,
                longitude=point.longitude,
            )
            for point in result.origins
        ),
        diagnostics=tuple(
            FlowDiagnosticResponse(
                code=diagnostic.code,
                message=diagnostic.message,
                subject=diagnostic.subject,
            )
            for diagnostic in result.diagnostics
        ),
    )


def cluster_markers(
    points: tuple[AttractionCluster, ...],
) -> tuple[SvgMarker, ...]:
    min_latitude = min(point.latitude for point in points)
    max_latitude = max(point.latitude for point in points)
    min_longitude = min(point.longitude for point in points)
    max_longitude = max(point.longitude for point in points)
    latitude_span = max_latitude - min_latitude or 1.0
    longitude_span = max_longitude - min_longitude or 1.0
    return tuple(
        SvgMarker(
            label=point.name,
            detail=f"Cluster {point.cluster}",
            x=50 + ((point.longitude - min_longitude) / longitude_span) * 800,
            y=470 - ((point.latitude - min_latitude) / latitude_span) * 420,
            radius=8,
            fill=CLUSTER_PALETTE[point.cluster % len(CLUSTER_PALETTE)],
        )
        for point in points
    )


def origin_markers(points: tuple[VisitorOrigin, ...]) -> tuple[SvgMarker, ...]:
    return tuple(
        SvgMarker(
            label=point.country,
            detail=f"{point.share_percent:.1f}% of visitors",
            x=50 + ((point.longitude + 180) / 360) * 800,
            y=50 + ((90 - point.latitude) / 180) * 420,
            radius=4 + min(12, sqrt(point.share_percent) * 2),
            fill="#3c78ff",
        )
        for point in points
    )


def run_analysis(request: Request, place: str, season: str) -> FlowResult:
    return request.app.state.flow_service.analyze(
        FlowQuery(place=place, season=season)
    )


@router.get(
    "/tourist_flow_analysis/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def tourist_flow_page(
    request: Request,
    place: str = DEFAULT_PLACE,
    season: str = DEFAULT_SEASON,
):
    service = request.app.state.flow_service
    try:
        result = run_analysis(request, place, season)
        error = None
        status_code = 200
    except FlowInputError as exc:
        result = None
        error = str(exc)
        status_code = 422
    return templates.TemplateResponse(
        request=request,
        name="flow_analysis.html",
        context={
            "title": "Tourist flow analysis",
            "result": result,
            "options": service.options(),
            "place": place,
            "season": season,
            "cluster_markers": cluster_markers(result.attractions) if result else (),
            "origin_markers": origin_markers(result.origins) if result else (),
            "error": error,
        },
        status_code=status_code,
    )


@router.get(
    "/api/v1/tourist-flow",
    response_model=TouristFlowResponse,
    tags=["flows"],
)
def tourist_flow_api(
    request: Request,
    place: str = DEFAULT_PLACE,
    season: str = DEFAULT_SEASON,
) -> TouristFlowResponse:
    try:
        return serialize_flow(run_analysis(request, place, season))
    except FlowInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
