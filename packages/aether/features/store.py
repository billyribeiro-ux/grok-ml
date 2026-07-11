"""Feature store writer — LaCie processed/ only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from aether.paths import FEATURE_STORE, ensure_processed_dirs, require_lacie


def write_feature_frame(
    df: pd.DataFrame,
    name: str,
    *,
    partition_cols: list[str] | None = None,
) -> Path:
    """
    Write a feature frame to LaCie feature store as parquet + manifest.

    Layout:
      feature_store/{name}/data.parquet
      feature_store/{name}/manifest.json
    """
    require_lacie()
    ensure_processed_dirs()
    if df.empty:
        raise ValueError(f"refusing to write empty feature frame: {name}")

    out_dir = FEATURE_STORE / name
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "data.parquet"
    df.to_parquet(data_path, index=False)

    manifest = {
        "name": name,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "symbols": sorted(df["symbol"].unique().tolist()) if "symbol" in df.columns else [],
        "date_min": str(df["date"].min()) if "date" in df.columns else None,
        "date_max": str(df["date"].max()) if "date" in df.columns else None,
        "path": str(data_path),
        "partition_cols": partition_cols or [],
        "feature_set": df["feature_set"].iloc[0] if "feature_set" in df.columns else None,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return data_path


def read_feature_frame(name: str) -> pd.DataFrame:
    require_lacie()
    path = FEATURE_STORE / name / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)
