from pathlib import Path
from unittest import TestCase

from cotour.recommendations import (
    RecommendationInputError,
    RecommendationQuery,
    RecommendationService,
    classify_origin,
)


DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"


class OriginClassificationTests(TestCase):
    def test_classifies_origin_without_network(self):
        self.assertEqual(classify_origin("Germany", "Munich"), "provenance_Munich")
        self.assertEqual(
            classify_origin("Germany", "Berlin"), "provenance_outside Munich"
        )
        self.assertEqual(
            classify_origin("France", None), "provenance_EU apart from GER"
        )
        self.assertEqual(
            classify_origin("Tunisia", None), "provenance_Outisde EU"
        )


class RecommendationServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RecommendationService(DATA_DIRECTORY)

    def test_default_query_returns_three_ranked_attractions(self):
        results = self.service.recommend(RecommendationQuery())

        self.assertEqual(len(results), 3)
        self.assertEqual([result.rank for result in results], [1, 2, 3])
        self.assertEqual(
            [result.name for result in results],
            ["Marienplatz", "Olympiapark", "Olympiastadion"],
        )
        self.assertTrue(all(result.name for result in results))
        self.assertTrue(all(result.address for result in results))
        self.assertNotIn("Allianz Arena", [result.name for result in results])

    def test_rejects_unknown_preference_before_scoring(self):
        with self.assertRaisesRegex(RecommendationInputError, "preference"):
            self.service.recommend(RecommendationQuery(preference="rooftops"))

    def test_rejects_unknown_city_for_every_country(self):
        with self.assertRaisesRegex(RecommendationInputError, "German city"):
            self.service.recommend(
                RecommendationQuery(country="Tunisia", german_city="Not a city")
            )

    def test_normalizes_allianz_arena_to_olympiastadion(self):
        query = RecommendationQuery(
            visit_type="with family",
            accommodation="Altstadt-Lehel",
            preference="indoors",
        )
        self.service._validate(query)
        candidates = self.service._combined_scores(query)

        self.assertNotIn("Allianz Arena", candidates.index)
        self.assertIn("Olympiastadion", candidates.index)

    def test_options_come_from_local_artifacts(self):
        options = self.service.options()

        self.assertIn("Tunisia", options.countries)
        self.assertIn("Munich", options.german_cities)
        self.assertIn("Maxvorstadt", options.districts)
