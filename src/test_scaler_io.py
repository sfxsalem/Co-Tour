import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.scaler_io import MODEL_DIRECTORY, SCALER_FILE, prediction_places


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
DATASET_FILE = ROOT_DIRECTORY / "data" / "Forecast Data" / "dataset.csv"


class PredictionArtifactTests(unittest.TestCase):
    def test_repository_models_and_scalers_match(self):
        scalers = json.loads(SCALER_FILE.read_text(encoding="utf-8"))
        dataset_columns = pd.read_csv(DATASET_FILE, nrows=0).columns.drop("DATE")

        places = prediction_places(dataset_columns, scalers)

        self.assertEqual(len(places), 18)
        self.assertEqual(set(places), set(scalers["yscalers"]))
        self.assertEqual(
            set(places),
            {model.stem for model in MODEL_DIRECTORY.glob("*.h5")},
        )

    def test_mismatched_artifacts_are_rejected(self):
        scalers = {"yscalers": {"Known Place": {}}}

        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "Different Place.h5").touch()

            with self.assertRaisesRegex(ValueError, "Forecast artifacts do not match"):
                prediction_places(["Known Place"], scalers, directory)


if __name__ == "__main__":
    unittest.main()
