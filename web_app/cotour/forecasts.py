"""Framework-independent tourist hotspot forecasting domain service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from cotour.artifacts import ArtifactBundle, load_artifact_bundle


DEFAULT_PREDICTED_MONTH = date(2020, 7, 1)
DEFAULT_HISTORICAL_MONTH = date(2020, 4, 1)
MARKER_COLORS = (
    "darkblue",
    "blue",
    "lightblue",
    "cadetblue",
    "green",
    "lightgreen",
    "orange",
    "lightred",
    "red",
    "darkred",
    "darkred",
)


class ForecastInputError(ValueError):
    """Raised when a requested month is not available in local artifacts."""


class ForecastDataError(RuntimeError):
    """Raised when a local forecast artifact violates the expected schema."""


@dataclass(frozen=True, slots=True)
class ForecastQuery:
    predicted_month: date = DEFAULT_PREDICTED_MONTH
    historical_month: date = DEFAULT_HISTORICAL_MONTH


@dataclass(frozen=True, slots=True)
class Hotspot:
    name: str
    latitude: float
    longitude: float
    weight: float
    intensity: float
    color: str


@dataclass(frozen=True, slots=True)
class ForecastOptions:
    predicted_months: tuple[date, ...]
    historical_months: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class ForecastResult:
    predicted_month: date
    historical_month: date
    predicted: tuple[Hotspot, ...]
    historical: tuple[Hotspot, ...]
    top_attractions: tuple[str, ...]


class ForecastService:
    """Load, validate, and query the repository's local forecast datasets."""

    def __init__(self, data_directory: Path | str | ArtifactBundle):
        self.artifacts = (
            data_directory
            if isinstance(data_directory, ArtifactBundle)
            else load_artifact_bundle(data_directory)
        )
        self.data_directory = self.artifacts.root
        self._predicted = self.artifacts.forecasts.predicted
        self._historical = self.artifacts.forecasts.historical
        self._coordinates = self.artifacts.forecasts.coordinates

    def options(self) -> ForecastOptions:
        return ForecastOptions(
            predicted_months=tuple(timestamp.date() for timestamp in self._predicted.index),
            historical_months=tuple(
                timestamp.date() for timestamp in self._historical.index
            ),
        )

    def forecast(self, query: ForecastQuery) -> ForecastResult:
        predicted = self._hotspots_for(
            self._predicted, query.predicted_month, kind="predicted"
        )
        historical = self._hotspots_for(
            self._historical, query.historical_month, kind="historical"
        )
        return ForecastResult(
            predicted_month=query.predicted_month,
            historical_month=query.historical_month,
            predicted=predicted,
            historical=historical,
            top_attractions=tuple(point.name for point in predicted[:10]),
        )

    def _hotspots_for(
        self, dataset: pd.DataFrame, requested_month: date, *, kind: str
    ) -> tuple[Hotspot, ...]:
        timestamp = pd.Timestamp(requested_month)
        if requested_month.day != 1 or timestamp not in dataset.index:
            raise ForecastInputError(
                f"The {kind} month {requested_month.isoformat()} is not available"
            )

        weights = dataset.loc[timestamp].rename("weight").dropna()
        joined = self._coordinates.join(weights, how="inner")
        joined = joined.sort_values(
            by=["weight"], ascending=False, kind="stable"
        )
        if joined.empty:
            raise ForecastDataError(f"No geocoded attractions exist for {kind} data")

        minimum = float(joined["weight"].min())
        maximum = float(joined["weight"].max())
        spread = maximum - minimum
        intensities = (
            (joined["weight"] - minimum) / spread
            if spread
            else pd.Series(0.0, index=joined.index)
        )

        return tuple(
            Hotspot(
                name=str(name),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                weight=float(row.weight),
                intensity=float(intensities.loc[name]),
                color=MARKER_COLORS[int(float(intensities.loc[name]) * 10)],
            )
            for name, row in joined.iterrows()
        )
