from datetime import date
from pathlib import Path
from unittest import TestCase

from cotour.forecasts import (
    ForecastInputError,
    ForecastQuery,
    ForecastService,
)


DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"


class ForecastServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = ForecastService(DATA_DIRECTORY)

    def test_options_come_from_local_forecast_artifacts(self):
        options = self.service.options()

        self.assertEqual(
            options.predicted_months,
            (
                date(2020, 7, 1),
                date(2020, 8, 1),
                date(2020, 9, 1),
                date(2020, 10, 1),
            ),
        )
        self.assertEqual(options.historical_months[0], date(2000, 1, 1))
        self.assertEqual(options.historical_months[-1], date(2020, 6, 1))
        self.assertEqual(len(options.historical_months), 246)

    def test_default_query_returns_ranked_geocoded_hotspots(self):
        result = self.service.forecast(ForecastQuery())

        self.assertEqual(result.predicted_month, date(2020, 7, 1))
        self.assertEqual(result.historical_month, date(2020, 4, 1))
        self.assertEqual(len(result.predicted), 23)
        self.assertEqual(len(result.historical), 23)
        self.assertIn("Munich Residenz", {point.name for point in result.predicted})
        self.assertEqual(
            result.top_attractions,
            (
                "Tierpark Hellabrunn",
                "Deutsches Museum",
                "Olympiastadion",
                "Olympiahalle",
                "Staatstheater am Gaertnerplatz",
                "Olympiapark",
                "Nationaltheater",
                "Neue Pinakothek",
                "Museum Brandhorst",
                "Olympiaturm",
            ),
        )

    def test_points_are_sorted_and_normalized_without_losing_raw_values(self):
        result = self.service.forecast(ForecastQuery())

        weights = [point.weight for point in result.predicted]
        intensities = [point.intensity for point in result.predicted]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertAlmostEqual(result.predicted[0].weight, 0.112239, places=6)
        self.assertEqual(max(intensities), 1.0)
        self.assertEqual(min(intensities), 0.0)
        self.assertTrue(all(0.0 <= intensity <= 1.0 for intensity in intensities))
        self.assertEqual(result.predicted[0].color, "darkred")
        self.assertEqual(result.predicted[-1].color, "darkblue")

    def test_rejects_unavailable_or_non_month_start_dates(self):
        invalid_queries = (
            ForecastQuery(predicted_month=date(2020, 6, 1)),
            ForecastQuery(predicted_month=date(2020, 7, 2)),
            ForecastQuery(historical_month=date(2020, 7, 1)),
        )

        for query in invalid_queries:
            with self.subTest(query=query), self.assertRaises(ForecastInputError):
                self.service.forecast(query)
