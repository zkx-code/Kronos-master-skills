#!/usr/bin/env python3
"""Validated CSV adapter for the bundled, unmodified Kronos predictor."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from runtime_support import model_locations, select_device

PRICE = ["open", "high", "low", "close"]
FEATURES = PRICE + ["volume", "amount"]
MODELS = {
    "mini": ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 2048),
    "small": ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 512),
    "base": ("NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base", 512),
}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--time-column", default="timestamps")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--future-csv", type=Path)
    mode.add_argument("--continuous-freq", help="Fixed bar interval for a 24/7 market only")
    mode.add_argument("--holdout", action="store_true")
    p.add_argument("--model", choices=MODELS, default="small")
    p.add_argument("--model-path")
    p.add_argument("--tokenizer-path")
    p.add_argument("--models-dir", type=Path, help="Parent of matching local model and tokenizer directories")
    p.add_argument("--model-revision")
    p.add_argument("--tokenizer-revision")
    p.add_argument("--lookback", type=int, default=400)
    p.add_argument("--pred-len", type=int, default=20)
    p.add_argument("--sample-count", type=int, default=1)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top-p", type=float, default=0.9)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto")
    p.add_argument("--timezone", default="unspecified", help="Descriptive timezone of naive input times")
    p.add_argument("--data-note", default="unspecified", help="Symbol, source, adjustment and units")
    p.add_argument("--price-only", action="store_true", help="Explicitly ignore volume/amount and use zeros")
    p.add_argument("--check-only", action="store_true", help="Validate inputs without loading model or writing forecasts")
    p.add_argument("--output-dir", type=Path)
    return p


def read_times(frame, column):
    if column not in frame:
        raise ValueError(f"Missing time column: {column}")
    if pd.api.types.is_numeric_dtype(frame[column]):
        raise ValueError("Numeric timestamps require explicit epoch-unit conversion before use")
    times = pd.to_datetime(frame[column], errors="raise")
    if not pd.api.types.is_datetime64_any_dtype(times):
        raise ValueError("Timestamps must use a single datetime format and timezone")
    if times.dt.tz is not None:
        raise ValueError("Convert timestamps to exchange-local naive time before use")
    if times.isna().any() or times.empty:
        raise ValueError("Timestamp column is empty or contains NaT")
    if times.duplicated().any() or not times.is_monotonic_increasing:
        raise ValueError("Timestamps must be strictly increasing and unique; input was not reordered")
    return times.reset_index(drop=True)


def quality(frame):
    invalid_ohlc = (
        (frame[PRICE] <= 0).any(axis=1)
        | (frame.high < frame[["open", "close", "low"]].max(axis=1))
        | (frame.low > frame[["open", "close", "high"]].min(axis=1))
    )
    return {
        "invalid_ohlc_rows": int(invalid_ohlc.sum()),
        "negative_volume_or_amount_rows": int((frame[["volume", "amount"]] < 0).any(axis=1).sum()),
    }


def prepare(args):
    context_limit = MODELS[args.model][2]
    if not 2 <= args.lookback <= context_limit:
        raise ValueError(f"lookback must be between 2 and {context_limit}")
    if not 1 <= args.pred_len <= context_limit:
        raise ValueError(f"pred-len must be between 1 and {context_limit}")
    if args.sample_count < 1:
        raise ValueError("sample-count must be positive")
    if not np.isfinite(args.temperature) or args.temperature <= 0 or not 0 < args.top_p <= 1:
        raise ValueError("temperature must be finite and positive; top-p must be in (0, 1]")
    if not 0 <= args.seed < 2**32:
        raise ValueError("seed must be between 0 and 2**32 - 1")
    if bool(args.model_path) != bool(args.tokenizer_path):
        raise ValueError("Provide model-path and tokenizer-path together")

    frame = pd.read_csv(args.csv)
    times = read_times(frame, args.time_column)
    columns = PRICE if args.price_only else FEATURES
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}; pure OHLC requires explicit --price-only")
    values = frame[columns].apply(pd.to_numeric, errors="raise").copy()
    if args.price_only:
        values["volume"] = 0.0
        values["amount"] = 0.0
    values = values[FEATURES].astype(float)
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError("Input contains missing or infinite feature values")
    faults = quality(values)
    if any(faults.values()):
        raise ValueError(f"Invalid input candles: {faults}; data was not repaired")

    stop = len(values) - args.pred_len if args.holdout else len(values)
    if stop < args.lookback:
        required = args.lookback + (args.pred_len if args.holdout else 0)
        raise ValueError(f"Need at least {required} rows; got {len(values)}")
    history = values.iloc[stop - args.lookback:stop].reset_index(drop=True)
    x_times = times.iloc[stop - args.lookback:stop].reset_index(drop=True)
    actual = None
    if args.holdout:
        y_times = times.iloc[stop:].reset_index(drop=True)
        actual = values.iloc[stop:].reset_index(drop=True)
    elif args.future_csv:
        y_times = read_times(pd.read_csv(args.future_csv), args.time_column)
    else:
        offset = pd.tseries.frequencies.to_offset(args.continuous_freq)
        step = pd.Timedelta(offset.nanos, unit="ns")
        if step <= pd.Timedelta(0):
            raise ValueError("continuous-freq must be a positive fixed interval")
        if not x_times.diff().iloc[1:].eq(step).all():
            raise ValueError("History has gaps or a different interval; provide verified future-csv times")
        y_times = pd.Series(pd.date_range(x_times.iloc[-1] + step, periods=args.pred_len, freq=offset))
    if len(y_times) != args.pred_len:
        raise ValueError(f"Future times must contain exactly {args.pred_len} rows; got {len(y_times)}")
    if y_times.iloc[0] <= x_times.iloc[-1]:
        raise ValueError("Future times must start strictly after history cutoff")
    return history, x_times, y_times, actual


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score(actual, predicted, last_close):
    truth = actual.close.to_numpy()
    error = predicted.close.to_numpy() - truth
    baseline_error = last_close - truth
    return {
        "close_mae": float(np.abs(error).mean()),
        "close_rmse": float(np.sqrt(np.mean(error**2))),
        "last_close_baseline_mae": float(np.abs(baseline_error).mean()),
        "last_close_baseline_rmse": float(np.sqrt(np.mean(baseline_error**2))),
        "rows": len(truth),
    }


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    history, x_times, y_times, actual = prepare(args)
    model_id, tokenizer_id, context_limit = MODELS[args.model]
    model_id, tokenizer_id = model_locations(args, model_id, tokenizer_id, Path(__file__).resolve().parents[3])
    report = {
        "status": "inputs_validated",
        "mode": "holdout" if args.holdout else "forecast",
        "input_csv": str(args.csv.resolve()),
        "input_sha256": sha256(args.csv),
        "future_csv_sha256": sha256(args.future_csv) if args.future_csv else None,
        "history_start": str(x_times.iloc[0]),
        "history_cutoff": str(x_times.iloc[-1]),
        "forecast_start": str(y_times.iloc[0]),
        "forecast_end": str(y_times.iloc[-1]),
        "model_id": model_id,
        "tokenizer_id": tokenizer_id,
        "volume_mode": "explicit_zero_volume" if args.price_only else "observed_volume_and_amount",
        "parameters": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
    }
    if args.check_only:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    if args.output_dir is None:
        p.error("--output-dir is required for inference")
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}; choose a new run directory")

    import torch

    core = Path(__file__).resolve().parents[1] / "assets" / "kronos"
    sys.path.insert(0, str(core))
    from model import Kronos, KronosPredictor, KronosTokenizer

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = select_device(torch, args.device)
    tokenizer_options = {"revision": args.tokenizer_revision} if args.tokenizer_revision else {}
    model_options = {"revision": args.model_revision} if args.model_revision else {}
    tokenizer = KronosTokenizer.from_pretrained(tokenizer_id, **tokenizer_options)
    model = Kronos.from_pretrained(model_id, **model_options)
    tokenizer.eval()
    model.eval()
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=context_limit)
    with torch.inference_mode():
        predicted = predictor.predict(
            df=history, x_timestamp=x_times, y_timestamp=y_times,
            pred_len=args.pred_len, T=args.temperature, top_p=args.top_p,
            sample_count=args.sample_count, verbose=True,
        )
    if list(predicted.columns) != FEATURES or len(predicted) != args.pred_len:
        raise ValueError("Unexpected prediction schema or row count")
    if not pd.DatetimeIndex(predicted.index).equals(pd.DatetimeIndex(y_times)):
        raise ValueError("Prediction timestamp alignment failed")
    if not np.isfinite(predicted.to_numpy()).all():
        raise ValueError("Model returned missing or infinite values")
    report.update({
        "status": "complete",
        "device": device,
        "versions": {name: importlib.metadata.version(name) for name in ["torch", "pandas", "numpy", "huggingface_hub"]},
        "forecast_quality": quality(predicted),
        "last_observed_close": float(history.close.iloc[-1]),
        "last_predicted_close": float(predicted.close.iloc[-1]),
        "predicted_close_change_pct": float((predicted.close.iloc[-1] / history.close.iloc[-1] - 1) * 100),
    })
    if actual is not None:
        report["evaluation"] = score(actual, predicted, history.close.iloc[-1])
    report_json = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    predicted.to_csv(args.output_dir / "forecast.csv", index_label="timestamps", encoding="utf-8-sig")
    if actual is not None:
        actual.index = pd.DatetimeIndex(y_times)
        actual.to_csv(args.output_dir / "actual.csv", index_label="timestamps", encoding="utf-8-sig")
    (args.output_dir / "run.json").write_text(report_json + "\n", encoding="utf-8")
    print(report_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
