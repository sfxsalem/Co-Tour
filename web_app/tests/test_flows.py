from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cotour.flows import (
    FlowDataError,
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

    def test_rejects_duplicate_cluster_rows_as_corrupt_artifacts(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_minimal_artifacts(root, duplicate_cluster=True)

            with self.assertRaises(FlowDataError):
                FlowService(root)

    def test_rejects_nonempty_origin_percentages_that_do_not_total_100(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_minimal_artifacts(root, origin_share=60)
            service = FlowService(root)

            with self.assertRaises(FlowDataError):
                service.analyze(FlowQuery(place="Sample Attraction"))

    @staticmethod
    def _write_minimal_artifacts(
        root: Path, *, duplicate_cluster: bool = False, origin_share: int = 100
    ) -> None:
        cluster_directory = root / "K_means_data"
        coordinate_directory = root / "geocoordinates"
        season_directory = root / "Tripadvisor_datasets" / "Seasons"
        cluster_directory.mkdir(parents=True)
        coordinate_directory.mkdir(parents=True)
        season_directory.mkdir(parents=True)

        cluster_rows = "Sample Attraction,0\n"
        if duplicate_cluster:
            cluster_rows += "Sample Attraction,1\n"
        (cluster_directory / "clusters.csv").write_text(
            "attraction_name,Cluster\n" + cluster_rows, encoding="utf-8"
        )
        (coordinate_directory / "TripAdvisor_geoattractions.csv").write_text(
            "place,latitude,longitude\nSample Attraction,48.14,11.58\n",
            encoding="utf-8",
        )
        for season in SEASON_CODES:
            (season_directory / f"Sample Attraction_{season}.csv").write_text(
                "country,flux density,latitude,longitude\n"
                f"Germany,{origin_share},51.08,10.42\n",
                encoding="utf-8",
            )
