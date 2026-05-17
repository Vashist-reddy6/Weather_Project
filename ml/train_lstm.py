"""
LSTM Sequence Model — WeatherGuard AI
======================================
Trains a Keras LSTM that classifies disaster risk (0-LOW → 3-CRITICAL) from
a 24-hour sliding window of meteorological features.

Why LSTM?
---------
XGBoost (train_unified.py) treats each hourly snapshot independently.
The LSTM sees the last 24 hours of weather evolution, which is how actual
forecasters detect developing cyclones / flood events — a prolonged pressure
drop combined with rising rainfall is more dangerous than a single-hour spike.

Output
------
ml/lstm_model.keras     — saved Keras model
ml/lstm_scaler.pkl      — StandardScaler fitted on training data (must travel
                          alongside the model for inference)
ml/lstm_model.meta.json — metadata for the predict router

Usage
-----
    python train_lstm.py                 # train from real_weather_data.csv
    python train_lstm.py --epochs 20     # quick smoke-test
"""

import argparse
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

# ── Optional Keras import with a helpful error ────────────────────────────────
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
except ImportError:
    print(
        "\n[ERROR] TensorFlow is not installed.\n"
        "  Run:  pip install tensorflow\n"
        "  (TF 2.13+ recommended; CPU-only build works fine for this model)\n"
    )
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE          = os.path.dirname(__file__)
CSV_PATH      = os.path.join(HERE, "real_weather_data.csv")
MODEL_OUT     = os.path.join(HERE, "lstm_model.keras")
SCALER_OUT    = os.path.join(HERE, "lstm_scaler.pkl")
META_OUT      = os.path.join(HERE, "lstm_model.meta.json")

FEATURES      = ["temperature", "humidity", "pressure", "wind_speed", "cloud_cover", "rainfall_1h"]
LABEL_COL     = "risk_label"
SEQ_LEN       = 24          # 24-hour look-back window
NUM_CLASSES   = 4           # LOW / MODERATE / HIGH / CRITICAL
RISK_NAMES    = {0: "LOW", 1: "MODERATE", 2: "HIGH", 3: "CRITICAL"}


# ── Sequence builder ──────────────────────────────────────────────────────────
def build_sequences(df: pd.DataFrame, seq_len: int):
    """Slide a window of *seq_len* rows over the DataFrame.

    Returns:
        X  — shape (N, seq_len, n_features)
        y  — shape (N,)  — label taken from the LAST row of each window
    """
    X, y = [], []
    data = df[FEATURES].values
    labels = df[LABEL_COL].values
    for i in range(seq_len, len(df)):
        X.append(data[i - seq_len : i])
        y.append(labels[i])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ── Model definition ─────────────────────────────────────────────────────────
def build_lstm_model(seq_len: int, n_features: int, n_classes: int) -> keras.Model:
    """Stacked LSTM with dropout regularisation."""
    inp = keras.Input(shape=(seq_len, n_features), name="weather_sequence")

    x = layers.LSTM(128, return_sequences=True, name="lstm_1")(inp)
    x = layers.Dropout(0.3)(x)
    x = layers.LSTM(64, return_sequences=False, name="lstm_2")(x)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(64, activation="relu", name="dense_1")(x)
    x = layers.Dense(32, activation="relu", name="dense_2")(x)
    out = layers.Dense(n_classes, activation="softmax", name="risk_class")(x)

    model = keras.Model(inputs=inp, outputs=out, name="WeatherGuardLSTM")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ── Training pipeline ─────────────────────────────────────────────────────────
def train(epochs: int = 30, batch_size: int = 256):
    # 1. Load data ─────────────────────────────────────────────────────────────
    if not os.path.exists(CSV_PATH):
        print(f"[ERROR] {CSV_PATH} not found.")
        print("  Run:  python download_data.py  first to download historical data.")
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH)
    df = df.dropna(subset=FEATURES + [LABEL_COL])

    if len(df) < SEQ_LEN + 1:
        print(f"[ERROR] Not enough rows ({len(df)}) for SEQ_LEN={SEQ_LEN}.")
        sys.exit(1)

    # Detect actual number of classes present in the data
    actual_classes = sorted(df[LABEL_COL].unique())
    actual_num_classes = len(actual_classes)
    print(f"  Classes present: {[RISK_NAMES.get(c, str(c)) for c in actual_classes]}")
    if actual_num_classes < NUM_CLASSES:
        print(f"  WARNING: Only {actual_num_classes}/4 risk classes found in data.")
        print("  This is normal if the dataset has no CRITICAL events.")

    print(f"  Rows: {len(df):,}   Label distribution:")
    print(df[LABEL_COL].value_counts().sort_index()
          .rename(index=RISK_NAMES).to_string())

    # 2. Scale features ────────────────────────────────────────────────────────
    scaler = StandardScaler()
    df[FEATURES] = scaler.fit_transform(df[FEATURES])
    joblib.dump(scaler, SCALER_OUT)
    print(f"\nScaler saved -> {SCALER_OUT}")

    # 3. Build sequences ───────────────────────────────────────────────────────
    print(f"\nBuilding {SEQ_LEN}-hour sequences ...")
    X, y = build_sequences(df, SEQ_LEN)
    print(f"  X shape: {X.shape}   y shape: {y.shape}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )

    # Use only classes that actually exist in the data
    actual_classes = sorted(np.unique(y))
    actual_num_classes = len(actual_classes)
    print(f"\nBuilding model for {actual_num_classes} classes: {[RISK_NAMES.get(c, str(c)) for c in actual_classes]}")

    # 4. Class weights (imbalanced dataset) ────────────────────────────────────
    from sklearn.utils.class_weight import compute_class_weight
    classes = np.unique(y_train)
    cw = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes.tolist(), cw.tolist()))
    print(f"\nClass weights: {class_weight}")

    # 5. Train
    model = build_lstm_model(SEQ_LEN, len(FEATURES), actual_num_classes)
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=5, restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5
        ),
    ]

    print(f"\nTraining LSTM ({epochs} epochs, batch={batch_size}) ...")
    history = model.fit(
        X_train, y_train,
        validation_split=0.15,
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=1,
    )

    # 6. Evaluate ──────────────────────────────────────────────────────────────
    y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
    unique = sorted(set(y_test) | set(y_pred))
    target_names = [RISK_NAMES[c] for c in unique]

    print("\n── Test Set Results ──────────────────────────────────────────")
    print(classification_report(y_test, y_pred, target_names=target_names))
    test_acc = float(np.mean(y_pred == y_test))
    print(f"Test accuracy: {test_acc:.4f}")

    # 7. Save model + metadata ─────────────────────────────────────────────────
    model.save(MODEL_OUT)
    print(f"\nLSTM model saved -> {MODEL_OUT}")

    meta = {
        "model_type":  "LSTM",
        "seq_len":     SEQ_LEN,
        "features":    FEATURES,
        "num_classes": NUM_CLASSES,
        "risk_names":  RISK_NAMES,
        "test_accuracy": round(test_acc, 4),
        "epochs_ran":  len(history.history["loss"]),
        "framework":   f"TensorFlow {tf.__version__}",
    }
    with open(META_OUT, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata saved -> {META_OUT}")
    print("Done!")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train WeatherGuard LSTM risk classifier")
    parser.add_argument("--epochs",     type=int, default=30,  help="Max training epochs (default 30)")
    parser.add_argument("--batch-size", type=int, default=256, help="Mini-batch size (default 256)")
    args = parser.parse_args()
    train(epochs=args.epochs, batch_size=args.batch_size)
