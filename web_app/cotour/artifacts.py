"""Authenticated, cross-validated runtime artifact snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

import pandas as pd


MANIFEST_NAME = "artifact-manifest.json"
SCHEMA_VERSION = 1
SEASON_CODES = (
    "summer_pre_covid",
    "winter_pre_covid",
    "summer_covid",
    "winter_covid",
)
FIXED_ARTIFACTS = {
    "recommendation.countries": "geocoordinates/country.csv",
    "recommendation.german_cities": "geocoordinates/germanCities.csv",
    "recommendation.catalog": "Recommendation data/rec_dataset.csv",
    "recommendation.users": "Recommendation data/user_data.csv",
    "recommendation.addresses": "geocoordinates/geoattractions.csv",
    "forecast.predicted": "Forecast Data/dataset_predicted.csv",
    "forecast.historical": "Forecast Data/dataset.csv",
    "forecast.coordinates": "geocoordinates/State_geoattractions.csv",
    "flow.clusters": "K_means_data/clusters.csv",
    "flow.coordinates": "geocoordinates/TripAdvisor_geoattractions.csv",
}
REQUIRED_COLUMNS = {
    "recommendation.countries": {"value"},
    "recommendation.german_cities": {"city"},
    "recommendation.catalog": {"place", "metric", "city_district", "type_door"},
    "recommendation.users": {"place_name"},
    "recommendation.addresses": {"place", "address"},
    "forecast.predicted": {"DATE"},
    "forecast.historical": {"DATE"},
    "forecast.coordinates": {"place", "latitude", "longitude"},
    "flow.clusters": {"attraction_name", "Cluster"},
    "flow.coordinates": {"place", "latitude", "longitude"},
}


class ArtifactBundleError(RuntimeError):
    """The runtime artifact release is missing, altered, or inconsistent."""


@dataclass(frozen=True, slots=True)
class ArtifactFile:
    key: str
    path: PurePosixPath
    sha256: str
    byte_count: int
    row_count: int
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: int
    bundle_version: str
    files: tuple[ArtifactFile, ...]
    allowed_ungeocoded_forecasts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecommendationArtifacts:
    countries: tuple[str, ...]
    german_cities: tuple[str, ...]
    catalog: pd.DataFrame
    users: pd.DataFrame
    predicted_forecasts: pd.DataFrame
    addresses: pd.Series


@dataclass(frozen=True, slots=True)
class ForecastArtifacts:
    predicted: pd.DataFrame
    historical: pd.DataFrame
    coordinates: pd.DataFrame


@dataclass(frozen=True, slots=True)
class FlowArtifacts:
    clusters: pd.DataFrame
    coordinates: pd.DataFrame
    origins: Mapping[tuple[str, str], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    root: Path
    manifest: ArtifactManifest
    recommendations: RecommendationArtifacts
    forecasts: ForecastArtifacts
    flows: FlowArtifacts

    def assert_ready(self) -> None:
        """Document that construction is the complete readiness boundary."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(root: Path) -> ArtifactManifest:
    try:
        payload = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        schema_version = int(payload["schema_version"])
        bundle_version = str(payload["bundle_version"])
        raw_files = payload["files"]
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ArtifactBundleError("Artifact manifest is missing or invalid") from exc
    if schema_version != SCHEMA_VERSION:
        raise ArtifactBundleError("Artifact manifest schema is unsupported")
    if not bundle_version.strip() or not isinstance(raw_files, list):
        raise ArtifactBundleError("Artifact manifest metadata is invalid")

    files: list[ArtifactFile] = []
    for raw in raw_files:
        try:
            files.append(
                ArtifactFile(
                    key=str(raw["key"]),
                    path=PurePosixPath(str(raw["path"])),
                    sha256=str(raw["sha256"]),
                    byte_count=int(raw["bytes"]),
                    row_count=int(raw["rows"]),
                    columns=tuple(str(column) for column in raw["columns"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactBundleError("Artifact manifest entry is invalid") from exc
    allowed = tuple(str(value) for value in payload.get("contracts", {}).get(
        "allowed_ungeocoded_forecasts", []
    ))
    return ArtifactManifest(schema_version, bundle_version, tuple(files), allowed)


def _safe_path(root: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ArtifactBundleError("Artifact manifest contains an unsafe path")
    path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ArtifactBundleError("Artifact manifest contains a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ArtifactBundleError(f"Artifact is missing: {relative.as_posix()}") from exc
    if root not in resolved.parents or not resolved.is_file():
        raise ArtifactBundleError("Artifact path escaped the bundle")
    return resolved


def _numeric(data: pd.DataFrame, columns: list[str], key: str) -> None:
    try:
        numeric = data[columns].apply(pd.to_numeric, errors="raise")
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactBundleError(f"Artifact contains nonnumeric values: {key}") from exc
    if not numeric.notna().all().all():
        raise ArtifactBundleError(f"Artifact contains nonfinite values: {key}")
    finite = numeric.map(lambda value: isfinite(float(value)))
    if not finite.all().all():
        raise ArtifactBundleError(f"Artifact contains nonfinite values: {key}")


def _require_unique(data: pd.DataFrame, column: str, key: str) -> None:
    if data[column].isna().any() or data[column].astype(str).str.strip().eq("").any():
        raise ArtifactBundleError(f"Artifact contains an empty identifier: {key}")
    if data[column].duplicated().any():
        raise ArtifactBundleError(f"Artifact contains duplicate identifiers: {key}")


def _validate_tables(
    tables: dict[str, pd.DataFrame], manifest: ArtifactManifest
) -> None:
    for key, required in REQUIRED_COLUMNS.items():
        missing = required.difference(tables[key].columns)
        if missing:
            raise ArtifactBundleError(f"Artifact is missing required columns: {key}")

    _require_unique(tables["recommendation.countries"], "value", "recommendation.countries")
    if tables["recommendation.german_cities"]["city"].isna().any() or tables[
        "recommendation.german_cities"
    ]["city"].astype(str).str.strip().eq("").any():
        raise ArtifactBundleError("German city catalog contains empty values")
    _require_unique(tables["recommendation.catalog"], "place", "recommendation.catalog")
    _require_unique(tables["recommendation.addresses"], "place", "recommendation.addresses")
    _require_unique(tables["forecast.coordinates"], "place", "forecast.coordinates")
    _require_unique(tables["flow.clusters"], "attraction_name", "flow.clusters")
    _require_unique(tables["flow.coordinates"], "place", "flow.coordinates")
    _numeric(tables["recommendation.catalog"], ["metric"], "recommendation.catalog")
    catalog = tables["recommendation.catalog"]
    if catalog[["city_district", "type_door"]].isna().any().any() or catalog[
        ["city_district", "type_door"]
    ].astype(str).map(str.strip).eq("").any().any():
        raise ArtifactBundleError("Recommendation catalog contains empty attributes")
    addresses = tables["recommendation.addresses"]
    if addresses["address"].isna().any() or addresses["address"].astype(
        str
    ).str.strip().eq("").any():
        raise ArtifactBundleError("Recommendation addresses contain empty values")

    users = tables["recommendation.users"]
    if users["place_name"].isna().any() or users["place_name"].astype(
        str
    ).str.strip().eq("").any():
        raise ArtifactBundleError("Recommendation profiles contain empty place names")
    feature_columns = list(users.columns[1:])
    required_features = {
        "provenance_EU apart from GER",
        "provenance_Munich",
        "provenance_Outisde EU",
        "provenance_outside Munich",
        "visit_Traveled solo",
    }
    if not required_features.issubset(feature_columns):
        raise ArtifactBundleError("Recommendation profile features are incomplete")
    _numeric(users, feature_columns, "recommendation.users")

    for key in ("forecast.predicted", "forecast.historical"):
        data = tables[key]
        try:
            dates = pd.to_datetime(data["DATE"], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ArtifactBundleError(f"Artifact contains invalid dates: {key}") from exc
        if dates.duplicated().any() or not dates.dt.is_month_start.all():
            raise ArtifactBundleError(f"Artifact contains invalid or duplicate months: {key}")
        value_columns = [column for column in data.columns if column not in {"DATE", "AnzahlFall"}]
        _numeric(data, value_columns, key)

    for key in ("forecast.coordinates", "flow.coordinates"):
        data = tables[key]
        _numeric(data, ["latitude", "longitude"], key)
        latitude = pd.to_numeric(data["latitude"])
        longitude = pd.to_numeric(data["longitude"])
        if not latitude.between(-90, 90).all() or not longitude.between(-180, 180).all():
            raise ArtifactBundleError(f"Artifact contains invalid coordinates: {key}")

    _numeric(tables["flow.clusters"], ["Cluster"], "flow.clusters")
    cluster_values = pd.to_numeric(tables["flow.clusters"]["Cluster"])
    if any(value < 0 or not float(value).is_integer() for value in cluster_values):
        raise ArtifactBundleError("Flow clusters must be non-negative integers")
    cluster_names = set(tables["flow.clusters"]["attraction_name"].astype(str))
    flow_coordinate_names = set(tables["flow.coordinates"]["place"].astype(str))
    if cluster_names != flow_coordinate_names:
        raise ArtifactBundleError("Flow cluster and coordinate catalogs do not match")

    recommendation_names = set(tables["recommendation.catalog"]["place"].astype(str))
    address_names = set(tables["recommendation.addresses"]["place"].astype(str))
    predicted_names = set(tables["forecast.predicted"].columns) - {"DATE"}
    historical_names = set(tables["forecast.historical"].columns) - {"DATE", "AnzahlFall"}
    if recommendation_names != predicted_names or recommendation_names - address_names:
        raise ArtifactBundleError("Recommendation artifact catalogs do not match")
    if predicted_names != historical_names:
        raise ArtifactBundleError("Forecast artifact catalogs do not match")
    forecast_coordinate_names = set(tables["forecast.coordinates"]["place"].astype(str))
    actual_ungeocoded = tuple(sorted(predicted_names - forecast_coordinate_names))
    if actual_ungeocoded != tuple(sorted(manifest.allowed_ungeocoded_forecasts)):
        raise ArtifactBundleError("Forecast coordinate exceptions do not match the artifacts")

    origin_keys = {key for key in tables if key.startswith("flow.origins:")}
    expected_origin_keys = {
        f"flow.origins:{place}:{season}"
        for place in flow_coordinate_names
        for season in SEASON_CODES
    }
    if origin_keys != expected_origin_keys:
        raise ArtifactBundleError("Flow origin artifact grid is incomplete")
    unknown_keys = set(tables).difference(FIXED_ARTIFACTS).difference(origin_keys)
    if unknown_keys:
        raise ArtifactBundleError("Artifact manifest contains unknown logical keys")
    for key in sorted(origin_keys):
        data = tables[key]
        required = {"country", "flux density", "latitude", "longitude"}
        if required.difference(data.columns):
            raise ArtifactBundleError(f"Artifact is missing required columns: {key}")
        if data.empty:
            continue
        _require_unique(data, "country", key)
        _numeric(data, ["flux density", "latitude", "longitude"], key)
        shares = pd.to_numeric(data["flux density"])
        latitude = pd.to_numeric(data["latitude"])
        longitude = pd.to_numeric(data["longitude"])
        if not latitude.between(-90, 90).all() or not longitude.between(-180, 180).all():
            raise ArtifactBundleError(f"Artifact contains invalid coordinates: {key}")
        if not shares.between(0, 100).all() or not isclose(
            float(shares.sum()), 100.0, abs_tol=0.05
        ):
            raise ArtifactBundleError(f"Flow origin shares are invalid: {key}")


def load_artifact_bundle(data_directory: Path | str) -> ArtifactBundle:
    """Load and validate one complete immutable runtime artifact release."""
    try:
        root = Path(data_directory).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ArtifactBundleError("Artifact bundle directory is missing") from exc
    if not root.is_dir():
        raise ArtifactBundleError("Artifact bundle root is not a directory")
    manifest = _read_manifest(root)
    keys = [entry.key for entry in manifest.files]
    paths = [entry.path.as_posix() for entry in manifest.files]
    if len(keys) != len(set(keys)) or len(paths) != len(set(paths)):
        raise ArtifactBundleError("Artifact manifest contains duplicate entries")
    resolved_paths = {entry.key: _safe_path(root, entry.path) for entry in manifest.files}

    expected_fixed_paths = {
        key: PurePosixPath(relative) for key, relative in FIXED_ARTIFACTS.items()
    }
    entries_by_key = {entry.key: entry for entry in manifest.files}
    for key, expected_path in expected_fixed_paths.items():
        if key not in entries_by_key or entries_by_key[key].path != expected_path:
            raise ArtifactBundleError("Fixed artifact mapping does not match the contract")
    for key, entry in entries_by_key.items():
        if not key.startswith("flow.origins:"):
            continue
        try:
            place, season = key.removeprefix("flow.origins:").rsplit(":", maxsplit=1)
        except ValueError as exc:
            raise ArtifactBundleError("Flow origin artifact key is invalid") from exc
        expected_path = PurePosixPath(
            "Tripadvisor_datasets", "Seasons", f"{place}_{season}.csv"
        )
        if season not in SEASON_CODES or entry.path != expected_path:
            raise ArtifactBundleError("Flow origin artifact mapping is invalid")

    declared = set(paths)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.csv")
        if path.is_file()
    }
    if actual - declared:
        raise ArtifactBundleError("Artifact bundle contains undeclared CSV files")
    if declared - actual:
        raise ArtifactBundleError("Artifact manifest declares missing CSV files")

    tables: dict[str, pd.DataFrame] = {}
    for entry in manifest.files:
        path = resolved_paths[entry.key]
        if path.stat().st_size != entry.byte_count or _sha256(path) != entry.sha256:
            raise ArtifactBundleError(f"Artifact integrity check failed: {entry.key}")
        try:
            table = pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as exc:
            raise ArtifactBundleError(f"Artifact cannot be parsed: {entry.key}") from exc
        if len(table) != entry.row_count or tuple(table.columns) != entry.columns:
            raise ArtifactBundleError(f"Artifact shape does not match manifest: {entry.key}")
        tables[entry.key] = table

    if set(FIXED_ARTIFACTS) - set(tables):
        raise ArtifactBundleError("Artifact bundle is missing fixed runtime inputs")
    _validate_tables(tables, manifest)

    predicted = tables["forecast.predicted"].copy()
    predicted["DATE"] = pd.to_datetime(predicted["DATE"])
    historical = tables["forecast.historical"].copy()
    historical["DATE"] = pd.to_datetime(historical["DATE"])
    forecast_coordinates = tables["forecast.coordinates"].loc[
        :, ["place", "latitude", "longitude"]
    ].copy()
    flow_origins = {
        tuple(key.removeprefix("flow.origins:").rsplit(":", maxsplit=1)): value.copy()
        for key, value in tables.items()
        if key.startswith("flow.origins:")
    }
    return ArtifactBundle(
        root=root,
        manifest=manifest,
        recommendations=RecommendationArtifacts(
            countries=tuple(tables["recommendation.countries"]["value"].astype(str)),
            german_cities=tuple(
                dict.fromkeys(
                    tables["recommendation.german_cities"]["city"].astype(str)
                )
            ),
            catalog=tables["recommendation.catalog"].copy(),
            users=tables["recommendation.users"].copy(),
            predicted_forecasts=predicted.copy(),
            addresses=tables["recommendation.addresses"].set_index("place")["address"].copy(),
        ),
        forecasts=ForecastArtifacts(
            predicted=predicted.set_index("DATE").sort_index(),
            historical=historical.drop(
                columns=["AnzahlFall"], errors="ignore"
            ).set_index("DATE").sort_index(),
            coordinates=forecast_coordinates.set_index("place"),
        ),
        flows=FlowArtifacts(
            clusters=tables["flow.clusters"].copy(),
            coordinates=tables["flow.coordinates"].copy(),
            origins=MappingProxyType(flow_origins),
        ),
    )


def _artifact_paths(root: Path) -> dict[str, Path]:
    paths = {key: root / relative for key, relative in FIXED_ARTIFACTS.items()}
    coordinates = pd.read_csv(paths["flow.coordinates"])
    for place in sorted(coordinates["place"].dropna().astype(str)):
        for season in SEASON_CODES:
            key = f"flow.origins:{place}:{season}"
            paths[key] = root / "Tripadvisor_datasets" / "Seasons" / f"{place}_{season}.csv"
    return paths


def build_manifest(root: Path, bundle_version: str) -> Path:
    """Generate manifest metadata explicitly for a reviewed artifact release."""
    root = root.resolve(strict=True)
    files = []
    for key, path in sorted(_artifact_paths(root).items()):
        table = pd.read_csv(path)
        files.append(
            {
                "key": key,
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "rows": len(table),
                "columns": list(table.columns),
            }
        )
    output = root / MANIFEST_NAME
    output.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "bundle_version": bundle_version,
                "contracts": {"allowed_ungeocoded_forecasts": ["Munich Residenz"]},
                "files": files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
