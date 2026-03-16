"""
ML Model — March Madness Bracket Prediction System

Three-model ensemble (XGBoost + LightGBM + Neural Net) with:
- Platt scaling calibration
- 5-fold CV on 2008–2024, 2025 holdout validation
- Benchmarks against chalk, KenPom-only, and historical baselines
- SHAP feature importance
- Models saved to /models/
"""

import logging
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from scipy.special import expit
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb

warnings.filterwarnings("ignore", category=UserWarning)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"
CALIB_DIR = OUTPUTS_DIR / "calibration_plots"

ENSEMBLE_WEIGHTS = {"xgb": 0.45, "lgb": 0.35, "nn": 0.20}


# =========================================================================
# 1. XGBOOST
# =========================================================================

def train_xgboost(X_train: np.ndarray, y_train: np.ndarray) -> xgb.XGBClassifier:
    """Train XGBoost classifier with regularized hyperparameters."""
    model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=10,
        reg_alpha=0.1,
        reg_lambda=1.0,
        gamma=0.1,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        use_label_encoder=False,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    return model


# =========================================================================
# 2. LIGHTGBM
# =========================================================================

def train_lightgbm(X_train: np.ndarray, y_train: np.ndarray) -> lgb.LGBMClassifier:
    """Train LightGBM classifier with regularized hyperparameters."""
    model = lgb.LGBMClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=20,
        feature_fraction=0.7,
        bagging_fraction=0.8,
        bagging_freq=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="binary",
        metric="binary_logloss",
        random_state=42,
        verbose=-1,
    )
    model.fit(X_train, y_train)
    return model


# =========================================================================
# 3. NEURAL NETWORK (PyTorch)
# =========================================================================

class BracketNet(nn.Module):
    """2 hidden layer neural network: 128→64, ReLU, dropout 0.5."""

    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x)


class NNWrapper:
    """Scikit-learn-compatible wrapper for BracketNet.

    Implements fit/predict/predict_proba so it works with
    CalibratedClassifierCV and the ensemble pipeline.
    """

    _estimator_type = "classifier"

    def __init__(self, input_dim: int, epochs: int = 300, lr: float = 0.001,
                 batch_size: int = 64, patience: int = 10):
        self.input_dim = input_dim
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.patience = patience
        self.model = None
        self.scaler = StandardScaler()
        self._median_vals = None  # for NaN imputation
        self.classes_ = np.array([0, 1])

    def _impute(self, X, fit=False):
        """Median imputation for NaN values (NN can't handle NaN)."""
        X = np.array(X, dtype=float)
        if fit:
            self._median_vals = np.nanmedian(X, axis=0)
        for col in range(X.shape[1]):
            mask = np.isnan(X[:, col])
            if mask.any():
                X[mask, col] = self._median_vals[col]
        return X

    def fit(self, X, y):
        X_imp = self._impute(X, fit=True)
        X_scaled = self.scaler.fit_transform(X_imp)
        X_t = torch.FloatTensor(X_scaled)
        y_t = torch.FloatTensor(y.astype(float)).unsqueeze(1)

        # Hold out 15% for early stopping
        n = len(X_t)
        n_val = max(1, int(n * 0.15))
        perm = torch.randperm(n)
        train_idx, val_idx = perm[n_val:], perm[:n_val]
        X_tr, y_tr = X_t[train_idx], y_t[train_idx]
        X_vl, y_vl = X_t[val_idx], y_t[val_idx]

        self.model = BracketNet(self.input_dim)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr,
                                     weight_decay=1e-3)
        criterion = nn.BCEWithLogitsLoss()
        dataset = torch.utils.data.TensorDataset(X_tr, y_tr)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size,
                                             shuffle=True)

        best_val_loss = float("inf")
        best_state = None
        patience_counter = 0

        for epoch in range(self.epochs):
            self.model.train()
            for X_batch, y_batch in loader:
                optimizer.zero_grad()
                logits = self.model(X_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()

            # Early stopping check
            self.model.eval()
            with torch.no_grad():
                val_logits = self.model(X_vl)
                val_loss = criterion(val_logits, y_vl).item()
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    break

        # Restore best model
        if best_state is not None:
            self.model.load_state_dict(best_state)
        return self

    def predict_proba(self, X):
        X_imp = self._impute(X, fit=False)
        X_scaled = self.scaler.transform(X_imp)
        X_t = torch.FloatTensor(X_scaled)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(X_t).squeeze(1).numpy()
        probs = expit(logits)
        return np.column_stack([1 - probs, probs])

    def predict(self, X):
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(int)

    def decision_function(self, X):
        X_imp = self._impute(X, fit=False)
        X_scaled = self.scaler.transform(X_imp)
        X_t = torch.FloatTensor(X_scaled)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(X_t).squeeze(1).numpy()
        return logits

    def get_params(self, deep=True):
        return {"input_dim": self.input_dim, "epochs": self.epochs,
                "lr": self.lr, "batch_size": self.batch_size,
                "patience": self.patience}

    def set_params(self, **params):
        for k, v in params.items():
            setattr(self, k, v)
        return self


def train_neural_net(X_train: np.ndarray, y_train: np.ndarray) -> NNWrapper:
    """Train the PyTorch neural network."""
    model = NNWrapper(input_dim=X_train.shape[1], epochs=200, lr=0.001,
                      batch_size=64)
    model.fit(X_train, y_train)
    return model


# =========================================================================
# 4. CALIBRATION
# =========================================================================

def calibrate_model(model, X_train: np.ndarray, y_train: np.ndarray,
                    name: str) -> CalibratedClassifierCV:
    """Apply Platt scaling calibration via CalibratedClassifierCV."""
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=3)
    calibrated.fit(X_train, y_train)
    log.info("  %s calibrated (Platt scaling, 3-fold)", name)
    return calibrated


def plot_calibration(models: dict, X_val: np.ndarray, y_val: np.ndarray,
                     save_dir: Path):
    """Generate reliability diagrams for each model and the ensemble."""
    save_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    for idx, (name, model) in enumerate(models.items()):
        if idx >= 4:
            break
        ax = axes[idx]
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X_val)[:, 1]
        else:
            probs = model(X_val)

        fraction_pos, mean_pred = calibration_curve(y_val, probs, n_bins=10,
                                                     strategy="uniform")
        ax.plot(mean_pred, fraction_pos, "o-", label=name)
        ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect")
        ax.set_xlabel("Predicted probability")
        ax.set_ylabel("True fraction")
        ax.set_title(f"{name} Calibration")
        ax.legend(loc="lower right")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    plt.tight_layout()
    path = save_dir / "calibration_plots.png"
    plt.savefig(path, dpi=150)
    plt.close()
    log.info("Calibration plots saved to %s", path)


# =========================================================================
# 5. ENSEMBLE
# =========================================================================

def ensemble_predict_proba(models: dict, X: np.ndarray) -> np.ndarray:
    """Weighted ensemble prediction: 45% XGB + 35% LGB + 20% NN."""
    probs = np.zeros(X.shape[0])
    for name, model in models.items():
        weight = ENSEMBLE_WEIGHTS[name]
        if hasattr(model, "predict_proba"):
            p = model.predict_proba(X)[:, 1]
        else:
            p = model(X)
        probs += weight * p
    return probs


# =========================================================================
# 6. VALIDATION & BENCHMARKS
# =========================================================================

def evaluate(y_true: np.ndarray, y_prob: np.ndarray, label: str) -> dict:
    """Compute accuracy, log loss, Brier score, and AUC."""
    y_pred = (y_prob >= 0.5).astype(int)
    acc = accuracy_score(y_true, y_pred)
    ll = log_loss(y_true, np.clip(y_prob, 1e-7, 1 - 1e-7))
    brier = brier_score_loss(y_true, y_prob)
    try:
        auc = roc_auc_score(y_true, y_prob)
    except ValueError:
        auc = 0.5
    metrics = {"label": label, "accuracy": acc, "log_loss": ll,
               "brier_score": brier, "auc": auc}
    log.info("  %s: acc=%.4f  log_loss=%.4f  brier=%.4f  auc=%.4f",
             label, acc, ll, brier, auc)
    return metrics


def cross_validate(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> dict:
    """Run 5-fold CV and return average metrics for the ensemble."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_tr, X_vl = X[train_idx], X[val_idx]
        y_tr, y_vl = y[train_idx], y[val_idx]

        xgb_model = train_xgboost(X_tr, y_tr)
        lgb_model = train_lightgbm(X_tr, y_tr)
        nn_model = train_neural_net(X_tr, y_tr)

        # Calibrate
        xgb_cal = calibrate_model(xgb_model, X_tr, y_tr, f"XGB-f{fold}")
        lgb_cal = calibrate_model(lgb_model, X_tr, y_tr, f"LGB-f{fold}")
        nn_cal = calibrate_model(nn_model, X_tr, y_tr, f"NN-f{fold}")

        models = {"xgb": xgb_cal, "lgb": lgb_cal, "nn": nn_cal}
        probs = ensemble_predict_proba(models, X_vl)
        metrics = evaluate(y_vl, probs, f"Fold {fold + 1}")
        fold_metrics.append(metrics)

    avg = {
        "label": f"{n_folds}-fold CV Average",
        "accuracy": np.mean([m["accuracy"] for m in fold_metrics]),
        "log_loss": np.mean([m["log_loss"] for m in fold_metrics]),
        "brier_score": np.mean([m["brier_score"] for m in fold_metrics]),
        "auc": np.mean([m["auc"] for m in fold_metrics]),
    }
    log.info("  CV AVG: acc=%.4f  log_loss=%.4f  brier=%.4f  auc=%.4f",
             avg["accuracy"], avg["log_loss"], avg["brier_score"], avg["auc"])
    return avg


def benchmark_chalk(games_df: pd.DataFrame, y: np.ndarray) -> dict:
    """Benchmark: always pick the higher seed (lower number)."""
    # Team A is higher seed if seed_a < seed_b
    chalk_probs = np.where(games_df["seed_a"] < games_df["seed_b"], 0.85,
                           np.where(games_df["seed_a"] > games_df["seed_b"], 0.15, 0.5))
    return evaluate(y, chalk_probs, "Chalk (always higher seed)")


def benchmark_kenpom_only(X_train: np.ndarray, y_train: np.ndarray,
                          X_test: np.ndarray, y_test: np.ndarray,
                          feature_names: list) -> dict:
    """Benchmark: logistic regression on AdjEM diff alone.
    Trained on training set, evaluated on test set."""
    from sklearn.linear_model import LogisticRegression
    adj_em_idx = feature_names.index("adj_em_diff")
    X_em_train = X_train[:, adj_em_idx].reshape(-1, 1)
    X_em_test = X_test[:, adj_em_idx].reshape(-1, 1)
    lr = LogisticRegression(random_state=42)
    lr.fit(X_em_train, y_train)
    probs = lr.predict_proba(X_em_test)[:, 1]
    return evaluate(y_test, probs, "KenPom AdjEM-only")


# =========================================================================
# 7. SHAP FEATURE IMPORTANCE
# =========================================================================

def compute_shap_importance(model, X: np.ndarray, feature_names: list,
                            save_dir: Path):
    """Compute and plot SHAP values for the XGBoost model."""
    save_dir.mkdir(parents=True, exist_ok=True)

    # Use the base XGBoost model (unwrap from CalibratedClassifierCV)
    base_model = model
    if hasattr(model, "calibrated_classifiers_"):
        base_model = model.calibrated_classifiers_[0].estimator
    elif hasattr(model, "estimators_"):
        base_model = model.estimators_[0]

    try:
        import shap
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(X)

        fig, ax = plt.subplots(figsize=(10, 8))
        shap.summary_plot(shap_values, X, feature_names=feature_names,
                         max_display=20, show=False)
        path = save_dir / "shap_importance.png"
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        log.info("SHAP importance plot saved to %s", path)

        # Also save bar chart
        fig, ax = plt.subplots(figsize=(10, 8))
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        sorted_idx = np.argsort(mean_abs_shap)[::-1][:20]
        ax.barh(range(20), mean_abs_shap[sorted_idx][::-1])
        ax.set_yticks(range(20))
        ax.set_yticklabels([feature_names[i] for i in sorted_idx][::-1])
        ax.set_xlabel("Mean |SHAP value|")
        ax.set_title("Top 20 Feature Importance (SHAP)")
        plt.tight_layout()
        path2 = save_dir / "shap_importance_bar.png"
        plt.savefig(path2, dpi=150, bbox_inches="tight")
        plt.close()
        log.info("SHAP bar chart saved to %s", path2)

    except Exception as e:
        log.warning("SHAP computation failed: %s", e)


# =========================================================================
# 8. MAIN TRAINING PIPELINE
# =========================================================================

def train_and_evaluate(
    X: np.ndarray,
    y: np.ndarray,
    games_df: pd.DataFrame,
    feature_names: list,
) -> tuple[dict, dict]:
    """Full training pipeline:
    1. Split into train (2008-2024) and holdout (2025)
    2. 5-fold CV on training set
    3. Train final models on full training set
    4. Evaluate on 2025 holdout
    5. Benchmark comparisons
    6. SHAP importance
    7. Save models

    Returns:
        models: Dict of calibrated models {"xgb", "lgb", "nn"}
        benchmark_results: Dict of all benchmark metrics
    """
    log.info("=" * 60)
    log.info("TRAINING ML MODEL")
    log.info("=" * 60)

    # --- Split by year ---
    train_mask = games_df["season"] < 2025
    holdout_mask = games_df["season"] == 2025

    X_train, y_train = X[train_mask], y[train_mask]
    X_holdout, y_holdout = X[holdout_mask], y[holdout_mask]
    games_holdout = games_df[holdout_mask]

    log.info("Training set: %d games (2008-2024)", len(X_train))
    log.info("Holdout set:  %d games (2025)", len(X_holdout))

    # --- 5-fold Cross Validation ---
    log.info("--- 5-Fold Cross Validation ---")
    cv_results = cross_validate(X_train, y_train, n_folds=5)

    # --- Train final models on full training set ---
    log.info("--- Training Final Models ---")
    xgb_model = train_xgboost(X_train, y_train)
    log.info("  XGBoost trained")
    lgb_model = train_lightgbm(X_train, y_train)
    log.info("  LightGBM trained")
    nn_model = train_neural_net(X_train, y_train)
    log.info("  Neural Net trained")

    # --- Calibrate ---
    log.info("--- Calibrating Models ---")
    xgb_cal = calibrate_model(xgb_model, X_train, y_train, "XGBoost")
    lgb_cal = calibrate_model(lgb_model, X_train, y_train, "LightGBM")
    nn_cal = calibrate_model(nn_model, X_train, y_train, "NeuralNet")

    calibrated_models = {"xgb": xgb_cal, "lgb": lgb_cal, "nn": nn_cal}

    # --- Holdout evaluation ---
    log.info("--- 2025 Holdout Evaluation ---")
    # Individual models
    for name, model in calibrated_models.items():
        probs = model.predict_proba(X_holdout)[:, 1]
        evaluate(y_holdout, probs, f"{name} (holdout)")

    # Ensemble
    ensemble_probs = ensemble_predict_proba(calibrated_models, X_holdout)
    holdout_results = evaluate(y_holdout, ensemble_probs, "ENSEMBLE (holdout)")

    # --- Benchmarks ---
    log.info("--- Benchmarks (2025 Holdout) ---")
    chalk_results = benchmark_chalk(games_holdout, y_holdout)
    kenpom_results = benchmark_kenpom_only(X_train, y_train, X_holdout, y_holdout,
                                           feature_names)

    # Vegas proxy: logistic regression on seed differential, trained on training set
    from sklearn.linear_model import LogisticRegression
    seed_diff = games_df["seed_a"].values - games_df["seed_b"].values
    seed_lr = LogisticRegression(random_state=42)
    seed_lr.fit(seed_diff[train_mask].reshape(-1, 1), y_train)
    vegas_probs = seed_lr.predict_proba(seed_diff[holdout_mask].reshape(-1, 1))[:, 1]
    vegas_results = evaluate(y_holdout, vegas_probs, "Vegas proxy (seed LR)")

    benchmark_results = {
        "cv": cv_results,
        "holdout_ensemble": holdout_results,
        "chalk": chalk_results,
        "kenpom_only": kenpom_results,
        "vegas_proxy": vegas_results,
    }

    # --- Calibration plots ---
    log.info("--- Generating Calibration Plots ---")
    plot_models = {
        "XGBoost": xgb_cal,
        "LightGBM": lgb_cal,
        "NeuralNet": nn_cal,
        "Ensemble": lambda X: ensemble_predict_proba(calibrated_models, X),
    }
    plot_calibration(plot_models, X_holdout, y_holdout, CALIB_DIR)

    # --- SHAP ---
    log.info("--- Computing SHAP Feature Importance ---")
    compute_shap_importance(xgb_cal, X_train, feature_names, OUTPUTS_DIR)

    # --- Save models ---
    log.info("--- Saving Models ---")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(xgb_cal, MODELS_DIR / "xgb_calibrated.pkl")
    joblib.dump(lgb_cal, MODELS_DIR / "lgb_calibrated.pkl")
    joblib.dump(nn_cal, MODELS_DIR / "nn_calibrated.pkl")
    joblib.dump({
        "weights": ENSEMBLE_WEIGHTS,
        "feature_names": feature_names,
        "cv_results": cv_results,
        "holdout_results": holdout_results,
        "benchmarks": benchmark_results,
    }, MODELS_DIR / "ensemble_config.pkl")
    log.info("Models saved to %s", MODELS_DIR)

    return calibrated_models, benchmark_results


# =========================================================================
# 9. PREDICTION INTERFACE
# =========================================================================

def load_trained_models() -> tuple[dict, dict]:
    """Load pre-trained models from /models/ directory."""
    xgb_cal = joblib.load(MODELS_DIR / "xgb_calibrated.pkl")
    lgb_cal = joblib.load(MODELS_DIR / "lgb_calibrated.pkl")
    nn_cal = joblib.load(MODELS_DIR / "nn_calibrated.pkl")
    config = joblib.load(MODELS_DIR / "ensemble_config.pkl")

    models = {"xgb": xgb_cal, "lgb": lgb_cal, "nn": nn_cal}
    return models, config


def predict_matchup(models: dict, feature_vector: np.ndarray) -> float:
    """Predict win probability for a single matchup."""
    if feature_vector.ndim == 1:
        feature_vector = feature_vector.reshape(1, -1)
    return ensemble_predict_proba(models, feature_vector)[0]


# =========================================================================
# CLI ENTRY POINT
# =========================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from data_pipeline import run_pipeline
    from features import build_historical_features, FEATURE_NAMES

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    # Load data and build features
    hist, curr, refs, bracket = run_pipeline()
    X, y = build_historical_features(hist, refs["seed_results"])

    # Train and evaluate
    models, benchmarks = train_and_evaluate(
        X.values, y.values, hist, FEATURE_NAMES
    )

    # Print summary
    print("\n" + "=" * 60)
    print("MODEL TRAINING SUMMARY")
    print("=" * 60)
    print(f"\n{'Metric':<30} {'Accuracy':>10} {'Log Loss':>10} {'Brier':>10} {'AUC':>10}")
    print("-" * 70)
    for key, result in benchmarks.items():
        label = result["label"]
        print(f"{label:<30} {result['accuracy']:>10.4f} {result['log_loss']:>10.4f} "
              f"{result['brier_score']:>10.4f} {result['auc']:>10.4f}")
