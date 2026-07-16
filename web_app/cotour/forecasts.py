"""Framework-independent tourist hotspot forecasting domain service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


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

    def __init__(self, data_directory: Path | str):
        self.data_directory = Path(data_directory).resolve()
        forecast_directory = self.data_directory / "Forecast Data"
        self._predicted = self._load_forecasts(
            forecast_directory / "dataset_predicted.csv"
        )
        self._historical = self._load_forecasts(
            forecast_directory / "dataset.csv", ignored_columns={"AnzahlFall"}
        )
        self._coordinates = self._load_coordinates(
            self.data_directory / "geocoordinates" / "State_geoattractions.csv"
        )

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

    @staticmethod
    def _load_forecasts(
        path: Path, *, ignored_columns: set[str] | None = None
    ) -> pd.DataFrame:
        try:
            dataset = pd.read_csv(path, parse_dates=["DATE"])
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise ForecastDataError(f"Unable to load forecast data from {path}") from exc

        dataset = dataset.drop(columns=list(ignored_columns or ()), errors="ignore")
        if dataset["DATE"].duplicated().any():
            raise ForecastDataError(f"Forecast data contains duplicate months: {path}")

        dataset = dataset.set_index("DATE").sort_index()
        if dataset.empty or not dataset.columns.size:
            raise ForecastDataError(f"Forecast data is empty: {path}")
        try:
            return dataset.apply(pd.to_numeric, errors="raise")
        except (TypeError, ValueError) as exc:
            raise ForecastDataError(f"Forecast weights must be numeric: {path}") from exc

    @staticmethod
    def _load_coordinates(path: Path) -> pd.DataFrame:
        try:
            coordinates = pd.read_csv(path)
            required = coordinates.loc[:, ["place", "latitude", "longitude"]].copy()
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise ForecastDataError(f"Unable to load attraction coordinates from {path}") from exc
        if required["place"].duplicated().any():
            raise ForecastDataError(f"Attraction coordinates contain duplicate places: {path}")
        required[["latitude", "longitude"]] = required[
            ["latitude", "longitude"]
        ].apply(pd.to_numeric, errors="coerce")
        return required.dropna().set_index("place")

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
