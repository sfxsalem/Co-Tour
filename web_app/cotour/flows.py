"""Framework-independent tourist flow analysis over local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cotour.artifacts import ArtifactBundle, load_artifact_bundle


DEFAULT_PLACE = "Olympiapark"
DEFAULT_SEASON = "summer_pre_covid"
MUNICH_LATITUDE_RANGE = (47.9, 48.4)
MUNICH_LONGITUDE_RANGE = (11.3, 11.8)


class FlowInputError(ValueError):
    """Raised when a requested catalog selection is unavailable."""


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

    def __init__(self, data_directory: Path | str | ArtifactBundle):
        self.artifacts = (
            data_directory
            if isinstance(data_directory, ArtifactBundle)
            else load_artifact_bundle(data_directory)
        )
        self.data_directory = self.artifacts.root
        places, self._attractions, self._diagnostics = self._load_attractions()
        self._options = FlowOptions(places=places, seasons=SEASON_OPTIONS)
        self._origin_cache: dict[tuple[str, str], tuple[VisitorOrigin, ...]] = {}

    def options(self) -> FlowOptions:
        return self._options

    def analyze(self, query: FlowQuery = FlowQuery()) -> FlowResult:
        if query.place not in self._options.places:
            raise FlowInputError("Unknown tourist-flow place")
        season_codes = {season.code for season in self._options.seasons}
        if query.season not in season_codes:
            raise FlowInputError("Unknown tourist-flow season")

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
        clusters = self.artifacts.flows.clusters.loc[
            :, ["attraction_name", "Cluster"]
        ].copy()
        coordinates = self.artifacts.flows.coordinates.loc[
            :, ["place", "latitude", "longitude"]
        ].copy()
        cluster_names = set(clusters["attraction_name"].astype(str))
        coordinate_names = set(coordinates["place"].astype(str))

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

    def _load_origins(self, place: str, season: str) -> tuple[VisitorOrigin, ...]:
        cache_key = (place, season)
        if cache_key in self._origin_cache:
            return self._origin_cache[cache_key]

        origins = self.artifacts.flows.origins[cache_key].loc[
            :, ["country", "flux density", "latitude", "longitude"]
        ].copy()
        if origins.empty:
            result: tuple[VisitorOrigin, ...] = ()
            self._origin_cache[cache_key] = result
            return result

        origins = origins.sort_values(
            ["flux density", "country"], ascending=[False, True], kind="stable"
        )
        result = tuple(
            VisitorOrigin(
                country=str(country),
                share_percent=float(share_percent),
                latitude=float(latitude),
                longitude=float(longitude),
            )
            for country, share_percent, latitude, longitude in origins.itertuples(
                index=False, name=None
            )
        )
        self._origin_cache[cache_key] = result
        return result
