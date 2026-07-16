import json
from pathlib import Path

import numpy as np


SCALER_FILE = Path(__file__).resolve().parents[1] / "data_scaler" / "scalers.json"


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


def transform(values, parameters):
    return (values - np.asarray(parameters["mean"])) / np.asarray(parameters["scale"])


def inverse_transform(values, parameters):
    return values * np.asarray(parameters["scale"]) + np.asarray(parameters["mean"])
