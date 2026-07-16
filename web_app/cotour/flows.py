"""Framework-independent tourist flow analysis over local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path

import pandas as pd


DEFAULT_PLACE = "Olympiapark"
DEFAULT_SEASON = "summer_pre_covid"
MUNICH_LATITUDE_RANGE = (47.9, 48.4)
MUNICH_LONGITUDE_RANGE = (11.3, 11.8)


class FlowInputError(ValueError):
    """Raised when a requested catalog selection is unavailable."""


class FlowDataError(RuntimeError):
    """Raised when a local tourist-flow artifact is malformed."""


@dataclass(frozen=True, slots=True)
class FlowQuery:
    place: str = DEFAULT_PLACE
    season: str = DEFAULT_SEASON


@dataclass(frozen=True, slots=True)
class SeasonOption:
    code: str
    label: str
    group: str


@dataclass(frozen=True, slots=True)
class FlowOptions:
    places: tuple[str, ...]
    seasons: tuple[SeasonOption, ...]


@dataclass(frozen=True, slots=True)
class AttractionCluster:
    name: str
    latitude: float
    longitude: float
    cluster: int


@dataclass(frozen=True, slots=True)
class VisitorOrigin:
    country: str
    share_percent: float
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class FlowDiagnostic:
    code: str
    message: str
    subject: str


@dataclass(frozen=True, slots=True)
class FlowResult:
    place: str
    season: str
    attractions: tuple[AttractionCluster, ...]
    origins: tuple[VisitorOrigin, ...]
    diagnostics: tuple[FlowDiagnostic, ...]


SEASON_OPTIONS = (
    SeasonOption("summer_pre_covid", "Summer 2019", "Pre-COVID"),
    SeasonOption("winter_pre_covid", "Winter 2019", "Pre-COVID"),
    SeasonOption("summer_covid", "Summer 2020", "COVID period"),
    SeasonOption("winter_covid", "Winter 2020", "COVID period"),
)


class FlowService:
    """Expose validated flow analysis without leaking pandas or file paths."""

    def __init__(self, data_directory: Path | str):
        self.data_directory = Path(data_directory).resolve()
        self._season_directory = (
            self.data_directory / "Tripadvisor_datasets" / "Seasons"
        ).resolve()
        places, self._attractions, self._diagnostics = self._load_attractions()
        self._options = FlowOptions(places=places, seasons=SEASON_OPTIONS)
        self._manifest = self._build_manifest()
        self._origin_cache: dict[tuple[str, str], tuple[VisitorOrigin, ...]] = {}

    def options(self) -> FlowOptions:
        return self._options

    def analyze(self, query: FlowQuery = FlowQuery()) -> FlowResult:
        if query.place not in self._options.places:
            raise FlowInputError(f"Unknown tourist-flow place: {query.place}")
        season_codes = {season.code for season in self._options.seasons}
        if query.season not in season_codes:
            raise FlowInputError(f"Unknown tourist-flow season: {query.season}")

        origins = self._load_origins(query.place, query.season)
        diagnostics = self._diagnostics
        if not origins:
            diagnostics += (
                FlowDiagnostic(
                    code="no-origin-data",
                    message="No visitor-origin observations are available for this selection.",
                    subject=f"{query.place}:{query.season}",
                ),
            )
        return FlowResult(
            place=query.place,
            season=query.season,
            attractions=self._attractions,
            origins=origins,
            diagnostics=diagnostics,
        )

    def _load_attractions(
        self,
    ) -> tuple[
        tuple[str, ...],
        tuple[AttractionCluster, ...],
        tuple[FlowDiagnostic, ...],
    ]:
        cluster_path = self.data_directory / "K_means_data" / "clusters.csv"
        coordinate_path = (
            self.data_directory
            / "geocoordinates"
            / "TripAdvisor_geoattractions.csv"
        )
        clusters = self._read_csv(cluster_path, {"attraction_name", "Cluster"})[
            ["attraction_name", "Cluster"]
        ].copy()
        coordinates = self._read_csv(
            coordinate_path, {"place", "latitude", "longitude"}
        )[["place", "latitude", "longitude"]].copy()

        self._require_unique(clusters, "attraction_name", cluster_path)
        self._require_unique(coordinates, "place", coordinate_path)
        clusters["Cluster"] = self._numeric_column(
            clusters, "Cluster", cluster_path
        )
        if any(value < 0 or not float(value).is_integer() for value in clusters["Cluster"]):
            raise FlowDataError(f"Cluster identifiers must be non-negative integers: {cluster_path}")
        coordinates["latitude"] = self._numeric_column(
            coordinates, "latitude", coordinate_path
        )
        coordinates["longitude"] = self._numeric_column(
            coordinates, "longitude", coordinate_path
        )
        self._require_coordinates(coordinates, coordinate_path)

        cluster_names = set(clusters["attraction_name"])
        coordinate_names = set(coordinates["place"])
        if cluster_names != coordinate_names:
            raise FlowDataError("Cluster and attraction-coordinate catalogs do not match")

        merged = clusters.merge(
            coordinates,
            left_on="attraction_name",
            right_on="place",
            how="inner",
            validate="one_to_one",
        )
        in_munich = merged["latitude"].between(*MUNICH_LATITUDE_RANGE) & merged[
            "longitude"
        ].between(*MUNICH_LONGITUDE_RANGE)
        diagnostics = tuple(
            FlowDiagnostic(
                code="attraction-outside-munich",
                message="Attraction omitted because its coordinates are outside Munich.",
                subject=str(row.attraction_name),
            )
            for row in merged.loc[~in_munich].itertuples(index=False)
        )
        valid = merged.loc[in_munich].sort_values(
            ["Cluster", "attraction_name"], kind="stable"
        )
        attractions = tuple(
            AttractionCluster(
                name=str(row.attraction_name),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                cluster=int(row.Cluster),
            )
            for row in valid.itertuples(index=False)
        )
        return tuple(sorted(coordinate_names)), attractions, diagnostics

    def _build_manifest(self) -> dict[tuple[str, str], Path]:
        if not self._season_directory.is_dir():
            raise FlowDataError(
                f"Tourist-flow season directory is missing: {self._season_directory}"
            )
        manifest: dict[tuple[str, str], Path] = {}
        for place in self._options.places:
            for season in self._options.seasons:
                path = (self._season_directory / f"{place}_{season.code}.csv").resolve()
                if path.parent != self._season_directory or not path.is_file():
                    raise FlowDataError(
                        f"Missing tourist-flow artifact for {place} and {season.code}"
                    )
                manifest[(place, season.code)] = path
        return manifest

    def _load_origins(self, place: str, season: str) -> tuple[VisitorOrigin, ...]:
        cache_key = (place, season)
        if cache_key in self._origin_cache:
            return self._origin_cache[cache_key]

        path = self._manifest[cache_key]
        origins = self._read_csv(
            path, {"country", "flux density", "latitude", "longitude"}
        )[["country", "flux density", "latitude", "longitude"]].copy()
        if origins.empty:
            result: tuple[VisitorOrigin, ...] = ()
            self._origin_cache[cache_key] = result
            return result

        self._require_unique(origins, "country", path)
        if origins["country"].isna().any() or origins["country"].astype(str).str.strip().eq("").any():
            raise FlowDataError(f"Visitor countries must be non-empty: {path}")
        for column in ("flux density", "latitude", "longitude"):
            origins[column] = self._numeric_column(origins, column, path)
        self._require_coordinates(origins, path)
        if not origins["flux density"].between(0, 100).all():
            raise FlowDataError(f"Visitor shares must be between 0 and 100: {path}")
        if not isclose(float(origins["flux density"].sum()), 100.0, abs_tol=0.05):
            raise FlowDataError(f"Visitor shares must total 100 percent: {path}")

        origins = origins.sort_values(
            ["flux density", "country"], ascending=[False, True], kind="stable"
        )
        result = tuple(
            VisitorOrigin(
                country=str(row.country),
                share_percent=float(row._1),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
            )
            for row in origins.itertuples(index=False)
        )
        self._origin_cache[cache_key] = result
        return result

    @staticmethod
    def _read_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
        try:
            data = pd.read_csv(path)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            raise FlowDataError(f"Unable to load tourist-flow artifact: {path}") from exc
        missing = required_columns.difference(data.columns)
        if missing:
            raise FlowDataError(
                f"Tourist-flow artifact is missing columns {sorted(missing)}: {path}"
            )
        return data

    @staticmethod
    def _require_unique(data: pd.DataFrame, column: str, path: Path) -> None:
        if data[column].isna().any() or data[column].duplicated().any():
            raise FlowDataError(f"{column} values must be present and unique: {path}")

    @staticmethod
    def _numeric_column(data: pd.DataFrame, column: str, path: Path) -> pd.Series:
        try:
            numeric = pd.to_numeric(data[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise FlowDataError(f"{column} values must be numeric: {path}") from exc
        if not numeric.map(lambda value: isfinite(float(value))).all():
            raise FlowDataError(f"{column} values must be finite: {path}")
        return numeric

    @staticmethod
    def _require_coordinates(data: pd.DataFrame, path: Path) -> None:
        if not data["latitude"].between(-90, 90).all() or not data[
            "longitude"
        ].between(-180, 180).all():
            raise FlowDataError(f"Coordinates are outside WGS84 bounds: {path}")
