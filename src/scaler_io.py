import json
from pathlib import Path

import numpy as np


SCALER_FILE = Path(__file__).resolve().parents[1] / "data_scaler" / "scalers.json"
MODEL_DIRECTORY = Path(__file__).resolve().parents[1] / "ML_models"


def _parameters(scaler):
    return {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}


def save_scalers(xscalers, yscaler, place):
    """Persist scaler parameters as inert JSON rather than executable pickle data."""
    if SCALER_FILE.exists():
        data = json.loads(SCALER_FILE.read_text(encoding="utf-8"))
    else:
        data = {"xscalers": {}, "yscalers": {}}

    data["xscalers"] = {str(key): _parameters(value) for key, value in xscalers.items()}
    data["yscalers"][place] = _parameters(yscaler)
    SCALER_FILE.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_scalers():
    return json.loads(SCALER_FILE.read_text(encoding="utf-8"))


def prediction_places(dataset_columns, scalers, model_directory=MODEL_DIRECTORY):
    """Return supported prediction places in dataset order after validating artifacts."""
    dataset_places = set(dataset_columns)
    scaler_places = set(scalers["yscalers"])
    model_places = {model.stem for model in Path(model_directory).glob("*.h5")}

    if scaler_places != model_places:
        missing_scalers = sorted(model_places - scaler_places)
        missing_models = sorted(scaler_places - model_places)
        raise ValueError(
            "Forecast artifacts do not match: "
            f"missing scalers={missing_scalers}, missing models={missing_models}"
        )

    unknown_places = sorted(scaler_places - dataset_places)
    if unknown_places:
        raise ValueError(f"Forecast places are absent from the dataset: {unknown_places}")

    return [place for place in dataset_columns if place in scaler_places]


def transform(values, parameters):
    return (values - np.asarray(parameters["mean"])) / np.asarray(parameters["scale"])


def inverse_transform(values, parameters):
    return values * np.asarray(parameters["scale"]) + np.asarray(parameters["mean"])
