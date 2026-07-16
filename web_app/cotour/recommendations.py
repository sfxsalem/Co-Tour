"""Tourism recommendation use case, independent of any web framework."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd
from countrygroups import EUROPEAN_UNION
from sklearn.cluster import KMeans
from sklearn.preprocessing import minmax_scale


VISIT_COLUMN_PREFIX = "visit_Traveled "
ORIGIN_MUNICH = "provenance_Munich"
ORIGIN_OUTSIDE_MUNICH = "provenance_outside Munich"
ORIGIN_EU = "provenance_EU apart from GER"
# The source artifact contains this historical spelling. Keep it at the boundary.
ORIGIN_OUTSIDE_EU = "provenance_Outisde EU"
PREFERENCES = ("indoors", "outdoors")
MUNICH_DISTRICTS = (
    "Altstadt-Lehel",
    "Ludwigsvorstadt-Isarvorstadt",
    "Maxvorstadt",
    "Schwabing-West",
    "Au-Haidhausen",
    "Sendling",
    "Sendling-Westpark",
    "Schwanthalerhöhe",
    "Neuhausen-Nymphenburg",
    "Muenchen-Moosach",
    "Milbertshofen-Am Hart",
    "Schwabing-Freimann",
    "Bogenhausen",
    "Berg am Laim",
    "Trudering-Riem",
    "Ramersdorf-Perlach",
    "Obergiesing",
    "Untergiesing-Harlaching",
    "Thalkirchen-Obersendling-Forstenried-Fürstenried-Solln",
    "Hadern",
    "Pasing-Obermenzing",
    "Aubing-Lochhausen-Langwied",
    "Allach-Untermenzing",
    "Feldmoching-Hasenbergl",
    "Laim",
)


class RecommendationInputError(ValueError):
    """Raised when a recommendation query is outside the supported data domain."""


@dataclass(frozen=True, slots=True)
class RecommendationQuery:
    country: str = "Tunisia"
    german_city: str = "Munich"
    visit_type: str = "solo"
    accommodation: str = "Maxvorstadt"
    visit_date: date = date(2020, 8, 10)
    preference: str = "outdoors"


@dataclass(frozen=True, slots=True)
class Recommendation:
    rank: int
    name: str
    address: str
    score: float


@dataclass(frozen=True, slots=True)
class RecommendationOptions:
    countries: tuple[str, ...]
    german_cities: tuple[str, ...]
    districts: tuple[str, ...]
    visit_types: tuple[str, ...]
    preferences: tuple[str, ...] = PREFERENCES


def classify_origin(country: str, german_city: str | None) -> str:
    """Map a country/city selection to the exact feature names in the model."""
    if country == "Germany":
        return ORIGIN_MUNICH if german_city == "Munich" else ORIGIN_OUTSIDE_MUNICH
    if country in EUROPEAN_UNION.names:
        return ORIGIN_EU
    return ORIGIN_OUTSIDE_EU


class RecommendationService:
    """Load local artifacts and rank attractions for a validated traveler profile."""

    def __init__(self, data_directory: Path):
        self.data_directory = Path(data_directory).resolve()

    def _read_csv(self, relative_path: str) -> pd.DataFrame:
        path = (self.data_directory / relative_path).resolve()
        if self.data_directory not in path.parents:
            raise RuntimeError("Recommendation artifact escaped the data directory")
        return pd.read_csv(path)

    @cached_property
    def _countries(self) -> tuple[str, ...]:
        values = self._read_csv("geocoordinates/country.csv")["value"]
        return tuple(values.dropna().astype(str))

    @cached_property
    def _german_cities(self) -> tuple[str, ...]:
        values = self._read_csv("geocoordinates/germanCities.csv")["city"]
        return tuple(dict.fromkeys(values.dropna().astype(str)))

    @cached_property
    def _recommendation_data(self) -> pd.DataFrame:
        return self._read_csv("Recommendation data/rec_dataset.csv")

    @cached_property
    def _user_data(self) -> pd.DataFrame:
        return self._read_csv("Recommendation data/user_data.csv")

    @cached_property
    def _forecast_data(self) -> pd.DataFrame:
        data = self._read_csv("Forecast Data/dataset_predicted.csv")
        data["DATE"] = pd.to_datetime(data["DATE"])
        return data

    @cached_property
    def _addresses(self) -> pd.Series:
        data = self._read_csv("geocoordinates/geoattractions.csv")
        return data.set_index("place")["address"]

    @cached_property
    def _model(self) -> KMeans:
        features = self._user_data.iloc[:, 1:]
        return KMeans(n_clusters=10, random_state=0, n_init=10).fit(features)

    @cached_property
    def _model_feature_names(self) -> tuple[str, ...]:
        return tuple(self._user_data.columns[1:])

    def options(self) -> RecommendationOptions:
        visit_types = tuple(
            name.removeprefix(VISIT_COLUMN_PREFIX)
            for name in self._model_feature_names
            if name.startswith(VISIT_COLUMN_PREFIX)
        )
        return RecommendationOptions(
            countries=self._countries,
            german_cities=self._german_cities,
            districts=MUNICH_DISTRICTS,
            visit_types=visit_types,
        )

    def _validate(self, query: RecommendationQuery) -> None:
        options = self.options()
        checks = (
            (query.country, options.countries, "country"),
            (query.visit_type, options.visit_types, "visit type"),
            (query.accommodation, options.districts, "accommodation"),
            (query.preference, options.preferences, "preference"),
        )
        for value, allowed, label in checks:
            if value not in allowed:
                raise RecommendationInputError(f"Unsupported {label}: {value}")
        if query.country == "Germany" and query.german_city not in options.german_cities:
            raise RecommendationInputError(
                f"Unsupported German city: {query.german_city}"
            )
        months = self._forecast_data["DATE"].dt.to_period("M")
        if pd.Period(query.visit_date, freq="M") not in set(months):
            raise RecommendationInputError(
                f"No forecast is available for {query.visit_date:%Y-%m}"
            )

    def _cluster_scores(self, query: RecommendationQuery) -> pd.Series:
        cluster_map = pd.DataFrame(
            {
                "cluster": self._model.labels_,
                "place_name": self._user_data["place_name"],
            }
        )
        origin = classify_origin(query.country, query.german_city)
        visit = f"{VISIT_COLUMN_PREFIX}{query.visit_type}"
        vector = np.zeros(len(self._model_feature_names))
        vector[self._model_feature_names.index(origin)] = 1
        vector[self._model_feature_names.index(visit)] = 1
        features = pd.DataFrame(
            vector.reshape(1, -1), columns=self._model_feature_names
        )
        cluster = int(self._model.predict(features)[0])
        scores = cluster_map.loc[cluster_map["cluster"] == cluster, "place_name"]
        scores = scores.value_counts(normalize=True)

        place_types = self._recommendation_data.set_index("place")["type_door"]
        matching_type = place_types.reindex(scores.index).eq(query.preference)
        scores = scores * np.where(matching_type.fillna(False), 2.0, 1.0)
        return pd.Series(minmax_scale(scores), index=scores.index, name="cluster_score")

    def _artifact_scores(self, query: RecommendationQuery) -> pd.Series:
        data = self._recommendation_data.copy().set_index("place")
        month = pd.Period(query.visit_date, freq="M")
        forecast_row = self._forecast_data.loc[
            self._forecast_data["DATE"].dt.to_period("M") == month
        ].iloc[0]
        forecast = forecast_row.drop(labels="DATE").astype(float)
        forecast.index.name = "place"

        preference_score = (
            data["city_district"].eq(query.accommodation).astype(float) * 20
            + data["type_door"].eq(query.preference).astype(float) * 50
        )
        raw_scores = (
            preference_score * 10
            + data["metric"].astype(float) * 0.00005
            + forecast.reindex(data.index).fillna(0) * 0.001
        )
        return pd.Series(
            minmax_scale(raw_scores), index=data.index, name="artifact_score"
        )

    def recommend(self, query: RecommendationQuery) -> tuple[Recommendation, ...]:
        self._validate(query)
        scores = pd.concat(
            [self._cluster_scores(query), self._artifact_scores(query)], axis=1
        )
        scores["score"] = scores.mean(axis=1, skipna=True)
        ranked = scores.sort_values("score", ascending=False).head(3)

        results = []
        for rank, (name, row) in enumerate(ranked.iterrows(), start=1):
            address = self._addresses.get(name)
            if not isinstance(address, str) or not address:
                raise RuntimeError(f"Missing address for recommended attraction: {name}")
            results.append(
                Recommendation(
                    rank=rank,
                    name=str(name),
                    address=address,
                    score=round(float(row["score"]), 6),
                )
            )
        return tuple(results)
