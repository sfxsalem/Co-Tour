import json
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
from unittest import TestCase

import pandas as pd

from cotour.artifacts import (
    ArtifactBundleError,
    build_manifest,
    load_artifact_bundle,
)


DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"


class ArtifactBundleTests(TestCase):
    def test_production_bundle_is_complete_and_cross_validated(self):
        bundle = load_artifact_bundle(DATA_DIRECTORY)

        self.assertEqual(bundle.manifest.schema_version, 1)
        self.assertEqual(len(bundle.manifest.files), 94)
        self.assertEqual(len(bundle.recommendations.catalog), 23)
        self.assertEqual(len(bundle.forecasts.predicted), 4)
        self.assertEqual(len(bundle.flows.origins), 84)
        self.assertEqual(bundle.manifest.allowed_ungeocoded_forecasts, ())
        residence = bundle.forecasts.coordinates.loc["Munich Residenz"]
        self.assertAlmostEqual(float(residence["latitude"]), 48.1411608)
        self.assertAlmostEqual(float(residence["longitude"]), 11.57904463904056)

    def test_changed_artifact_fails_integrity_before_parsing(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            artifact = copied / "Recommendation data" / "rec_dataset.csv"
            artifact.write_bytes(artifact.read_bytes() + b"\n")

            with self.assertRaisesRegex(ArtifactBundleError, "integrity"):
                load_artifact_bundle(copied)

    def test_undeclared_runtime_csv_is_rejected(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            (copied / "unexpected.csv").write_text("value\n1\n", encoding="utf-8")

            with self.assertRaisesRegex(ArtifactBundleError, "undeclared"):
                load_artifact_bundle(copied)

    def test_unsupported_manifest_schema_is_rejected(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            manifest_path = copied / "artifact-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 2
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ArtifactBundleError, "unsupported"):
                load_artifact_bundle(copied)

    def test_manifest_path_traversal_is_rejected(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            manifest_path = copied / "artifact-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["path"] = "../outside.csv"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ArtifactBundleError, "unsafe"):
                load_artifact_bundle(copied)

    def test_duplicate_flow_cluster_is_rejected_at_bundle_boundary(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            path = copied / "K_means_data" / "clusters.csv"
            clusters = pd.read_csv(path)
            clusters = pd.concat([clusters, clusters.iloc[[0]]], ignore_index=True)
            clusters.to_csv(path, index=False)
            build_manifest(copied, "test-corrupt-cluster")

            with self.assertRaisesRegex(ArtifactBundleError, "duplicate"):
                load_artifact_bundle(copied)

    def test_invalid_flow_origin_total_is_rejected_at_bundle_boundary(self):
        with TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "data"
            copytree(DATA_DIRECTORY, copied)
            path = (
                copied
                / "Tripadvisor_datasets"
                / "Seasons"
                / "Olympiapark_summer_pre_covid.csv"
            )
            origins = pd.read_csv(path)
            origins.loc[0, "flux density"] = 60
            origins.to_csv(path, index=False)
            build_manifest(copied, "test-corrupt-origin")

            with self.assertRaisesRegex(ArtifactBundleError, "shares"):
                load_artifact_bundle(copied)
