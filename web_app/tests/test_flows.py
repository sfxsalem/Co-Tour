from pathlib import Path
from unittest import TestCase

from cotour.flows import (
    FlowInputError,
    FlowQuery,
    FlowService,
)


DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"
SEASON_CODES = (
    "summer_pre_covid",
    "winter_pre_covid",
    "summer_covid",
    "winter_covid",
)


class FlowServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = FlowService(DATA_DIRECTORY)

    def test_options_are_derived_from_complete_local_artifacts(self):
        options = self.service.options()

        self.assertEqual(len(options.places), 21)
        self.assertEqual(options.places, tuple(sorted(options.places)))
        self.assertIn("English Garden", options.places)
        self.assertEqual(
            tuple(season.code for season in options.seasons), SEASON_CODES
        )
        self.assertEqual(options.seasons[0].label, "Summer 2019")
        self.assertEqual(options.seasons[2].group, "COVID period")

    def test_default_analysis_is_ranked_deterministic_and_diagnostic(self):
        result = self.service.analyze(FlowQuery())

        self.assertEqual(result.place, "Olympiapark")
        self.assertEqual(result.season, "summer_pre_covid")
        self.assertEqual(len(result.attractions), 20)
        self.assertEqual(len(result.origins), 23)
        self.assertEqual(result.origins[0].country, "Germany")
        self.assertAlmostEqual(result.origins[0].share_percent, 32.876712, places=6)
        self.assertEqual(
            [(point.cluster, point.name) for point in result.attractions],
            sorted((point.cluster, point.name) for point in result.attractions),
        )
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, "attraction-outside-munich")
        self.assertEqual(result.diagnostics[0].subject, "English Garden")

    def test_every_catalog_combination_loads_and_empty_files_are_valid(self):
        options = self.service.options()
        empty_results = 0

        for place in options.places:
            for season in options.seasons:
                with self.subTest(place=place, season=season.code):
                    result = self.service.analyze(
                        FlowQuery(place=place, season=season.code)
                    )
                    self.assertEqual(result.place, place)
                    self.assertEqual(result.season, season.code)
                    empty_results += not result.origins

        self.assertEqual(empty_results, 7)

    def test_rejects_unknown_place_or_season_before_loading(self):
        invalid_queries = (
            FlowQuery(place="../../Recommendation data/rec"),
            FlowQuery(season="monsoon"),
        )

        for query in invalid_queries:
            with self.subTest(query=query), self.assertRaises(FlowInputError):
                self.service.analyze(query)

    def test_invalid_selection_error_does_not_reflect_attacker_input(self):
        attacker_value = "<script>alert(1)</script>" * 10

        with self.assertRaises(FlowInputError) as captured:
            self.service.analyze(FlowQuery(place=attacker_value))

        self.assertNotIn(attacker_value, str(captured.exception))
