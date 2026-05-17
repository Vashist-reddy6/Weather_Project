"""
WeatherGuard AI — Auto-Retraining Pipeline
==========================================
Re-fits the XGBoost disaster model every 7 days on the latest combination of:
  1. Base historical CSV (real_weather_data.csv)
  2. Recent predictions stored in SQLite (disaster_alerts.db)

Usage:
    python retrain_scheduler.py              # only retrains if model is >7 days old
    python retrain_scheduler.py --force      # always retrains
    python retrain_scheduler.py --dry-run    # validate data, skip model write

Run via cron (Linux/Mac):
    0 2 */7 * *  cd /app && python ml/retrain_scheduler.py >> logs/retrain.log 2>&1

Run via Windows Task Scheduler:
    Action: python C:\Hack-Weatherproj\ml\retrain_scheduler.py
    Trigger: Weekly, 02:00 AM
"""

import os
import sys
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# ── Configure logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("retrain")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
ML_DIR     = ROOT / "ml"
DB_PATH    = ROOT / "backend" / "disaster_alerts.db"
MODEL_PATH = ML_DIR / "disaster_model.pkl"
DATA_CSV   = ML_DIR / "real_weather_data.csv"

INTERVAL_DAYS = 7      # Retrain threshold
FEATURE_COLS  = ["temperature", "humidity", "pressure", "wind_speed", "cloud_cover", "rainfall_1h"]
LABEL_MAP     = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}


# ── Data helpers ──────────────────────────────────────────────────────────────

def fetch_db_records(limit: int = 5000) -> list[dict]:
    """Pull recent predictions from SQLite as additional training samples."""
    if not DB_PATH.exists():
        log.warning(f"Database not found at {DB_PATH} — skipping DB fetch")
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        log.info(f"Fetched {len(rows)} prediction records from DB")
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning(f"DB fetch failed: {exc}")
        return []


def build_df_from_db(records: list[dict]):
    """Convert DB prediction records to a training DataFrame."""
    import pandas as pd

    rows = []
    for r in records:
        try:
            w = json.loads(r.get("weather_data", "{}"))
            risk = r.get("risk_level", "")
            if risk not in LABEL_MAP:
                continue
            rows.append({
                "temperature":  float(w.get("temperature", 0)),
                "humidity":     float(w.get("humidity", 50)),
                "pressure":     float(w.get("pressure", 1013)),
                "wind_speed":   float(w.get("wind_speed", 0)),
                "cloud_cover":  float(w.get("cloud_cover", 0)),
                "rainfall_1h":  float(w.get("rainfall_1h", 0)),
                "label":        LABEL_MAP[risk],
            })
        except Exception:
            continue

    return pd.DataFrame(rows) if rows else None


def load_base_csv():
    """Load and label the base historical CSV if it exists."""
    import pandas as pd

    if not DATA_CSV.exists():
        log.warning(f"Base CSV not found at {DATA_CSV}")
        return None

    df = pd.read_csv(DATA_CSV)
    log.info(f"Loaded base CSV: {len(df)} rows, columns: {list(df.columns)}")

    # If CSV already has a numeric 'label' column, use it directly
    if "label" in df.columns and all(c in df.columns for c in FEATURE_COLS):
        return df[FEATURE_COLS + ["label"]].dropna()

    # If it has a numeric 'risk_label' column, use it directly
    if "risk_label" in df.columns and all(c in df.columns for c in FEATURE_COLS):
        df["label"] = df["risk_label"]
        log.info(f"Used existing numeric 'risk_label'")
        return df[FEATURE_COLS + ["label"]].dropna()

    # If it has a text risk_level / class column, map it
    for col in ("risk_level", "class", "disaster_risk", "target"):
        if col in df.columns:
            df["label"] = df[col].map(LABEL_MAP)
            df = df.dropna(subset=["label"])
            if all(c in df.columns for c in FEATURE_COLS):
                log.info(f"Mapped '{col}' → numeric label")
                return df[FEATURE_COLS + ["label"]]

    log.warning("Base CSV columns don't match expected schema — skipping")
    return None


def combine_datasets(df_base, df_db):
    """Merge base CSV and DB data, removing duplicates."""
    import pandas as pd

    parts = [p for p in [df_base, df_db] if p is not None and len(p) > 0]
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates()
    df["label"] = df["label"].astype(int)
    return df


# ── Retraining ────────────────────────────────────────────────────────────────

def retrain(dry_run: bool = False) -> bool:
    """Full retraining pipeline. Returns True on success."""
    log.info("=" * 60)
    log.info("WeatherGuard AI — Auto-Retraining Pipeline")
    log.info(f"Timestamp : {datetime.utcnow().isoformat()}Z")
    log.info(f"Dry-run   : {dry_run}")
    log.info("=" * 60)

    # 1. Gather data
    db_records = fetch_db_records()
    df_db      = build_df_from_db(db_records)
    df_base    = load_base_csv()

    df = combine_datasets(df_base, df_db)

    if df is None or len(df) < 50:
        log.error(
            f"Insufficient training data ({len(df) if df is not None else 0} rows). "
            "Need at least 50 rows. Aborting."
        )
        return False

    log.info(f"Combined dataset: {len(df)} rows")
    log.info(f"Class distribution:\n{df['label'].value_counts().to_string()}")

    if dry_run:
        log.info("DRY-RUN — skipping model training and write.")
        return True

    # 2. Train
    try:
        from xgboost import XGBClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score
        import joblib
        import numpy as np
    except ImportError as e:
        log.error(f"Missing dependency: {e}. Run: pip install xgboost scikit-learn joblib")
        return False

    X = df[FEATURE_COLS].fillna(0)
    y = df["label"].astype(int)

    # Stratify only if every class has ≥2 samples
    unique, counts = np.unique(y, return_counts=True)
    can_stratify   = all(c >= 2 for c in counts)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42,
        stratify=y if can_stratify else None,
    )

    log.info(f"Training: {len(X_train)} samples  |  Test: {len(X_test)} samples")

    model = XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.07,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="multi:softprob",
        num_class=4,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=["LOW", "MODERATE", "HIGH", "CRITICAL"],
        zero_division=0,
    )
    log.info(f"Test Accuracy: {acc:.4f}")
    log.info(f"Classification Report:\n{report}")

    # 3. Backup old model
    if MODEL_PATH.exists():
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup = MODEL_PATH.with_name(f"disaster_model_bak_{ts}.pkl")
        MODEL_PATH.rename(backup)
        log.info(f"Old model backed up → {backup.name}")

    # 4. Save new model
    joblib.dump(model, MODEL_PATH)
    log.info(f"✅ New model saved → {MODEL_PATH.name}")
    log.info(f"   Feature columns : {FEATURE_COLS}")
    log.info(f"   Training rows   : {len(X_train)}")
    log.info(f"   Test accuracy   : {acc:.4f}")

    # 5. Write a metadata sidecar
    meta = {
        "trained_at":      datetime.utcnow().isoformat() + "Z",
        "training_rows":   int(len(X_train)),
        "test_rows":       int(len(X_test)),
        "test_accuracy":   round(float(acc), 4),
        "features":        FEATURE_COLS,
        "n_estimators":    250,
        "interval_days":   INTERVAL_DAYS,
    }
    meta_path = MODEL_PATH.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info(f"Metadata written → {meta_path.name}")

    return True


# ── Scheduler logic ───────────────────────────────────────────────────────────

def model_age_hours() -> float | None:
    """Return age of the model file in hours, or None if it doesn't exist."""
    if not MODEL_PATH.exists():
        return None
    age = datetime.now() - datetime.fromtimestamp(MODEL_PATH.stat().st_mtime)
    return age.total_seconds() / 3600


def should_retrain() -> bool:
    age = model_age_hours()
    if age is None:
        log.info("No model file found — will train from scratch")
        return True
    threshold = INTERVAL_DAYS * 24
    if age > threshold:
        log.info(f"Model is {age:.1f}h old (threshold={threshold}h) — retraining")
        return True
    log.info(f"Model is fresh ({age:.1f}h old, threshold={threshold}h) — skipping")
    return False


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    force   = "--force"   in sys.argv
    dry_run = "--dry-run" in sys.argv

    if force:
        log.info("--force flag set — forcing retraining regardless of model age")

    if force or should_retrain():
        ok = retrain(dry_run=dry_run)
        sys.exit(0 if ok else 1)
    else:
        sys.exit(0)
