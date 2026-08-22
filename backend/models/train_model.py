# backend/models/train_model.py
# RecoverIQ — Payment Failure Prediction Model Training
# Trains a Gradient Boosted classifier on synthetic Indian payment data
# Outputs: trained model (.joblib), performance metrics, feature importance

import os
import sys
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data_generator import generate_batch, generate_feature_matrix

warnings.filterwarnings("ignore")


# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "failure_predictor.joblib")
SCALER_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "feature_scaler.joblib")
METRICS_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "model_metrics.json")

TRAINING_SAMPLES = 5000       # Large enough for stable cross-validation
RANDOM_SEED = 42
N_FOLDS = 5                   # Stratified 5-fold CV

# GradientBoosting hyperparameters (tuned for this problem)
MODEL_PARAMS = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.1,
    "min_samples_split": 20,
    "min_samples_leaf": 10,
    "subsample": 0.8,
    "max_features": "sqrt",
    "random_state": RANDOM_SEED,
}


# =============================================================================
# TRAINING PIPELINE
# =============================================================================

def train_model() -> dict:
    """
    Complete training pipeline:
    1. Generate synthetic data
    2. Engineer features
    3. Train with stratified k-fold CV
    4. Evaluate metrics
    5. Save model and scaler
    
    Returns:
        dict with performance metrics
    """
    print("=" * 60)
    print("RecoverIQ — Model Training Pipeline")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Step 1: Generate Training Data
    # -------------------------------------------------------------------------
    print("\n📊 Step 1: Generating synthetic training data...")
    df = generate_batch(n=TRAINING_SAMPLES, seed=RANDOM_SEED)

    total = len(df)
    failed = df["is_failed"].sum()
    print(f"   Total transactions: {total}")
    print(f"   Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"   Successful: {total - failed} ({(total-failed)/total*100:.1f}%)")

    # -------------------------------------------------------------------------
    # Step 2: Feature Engineering
    # -------------------------------------------------------------------------
    print("\n🧬 Step 2: Engineering features...")
    X = generate_feature_matrix(df)
    y = df["is_failed"].values

    feature_names = list(X.columns)
    print(f"   Features ({len(feature_names)}): {feature_names}")
    print(f"   Feature matrix shape: {X.shape}")
    print(f"   Class distribution: {np.bincount(y)}")

    # -------------------------------------------------------------------------
    # Step 3: Stratified K-Fold Cross-Validation
    # -------------------------------------------------------------------------
    print(f"\n🔄 Step 3: {N_FOLDS}-Fold Stratified Cross-Validation...")

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)

    # Scoring metrics for cross-validation
    scoring = {
        "auc_roc": "roc_auc",
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "accuracy": "accuracy",
    }

    model = GradientBoostingClassifier(**MODEL_PARAMS)

    cv_results = cross_validate(
        model,
        X.values,
        y,
        cv=skf,
        scoring=scoring,
        return_train_score=True,
        n_jobs=-1,
    )

    # Print fold-by-fold results
    print(f"\n   {'Fold':<6} {'AUC-ROC':<10} {'Precision':<12} {'Recall':<10} {'F1':<10} {'Accuracy':<10}")
    print("   " + "-" * 58)
    for i in range(N_FOLDS):
        print(
            f"   {i+1:<6} "
            f"{cv_results['test_auc_roc'][i]:<10.4f} "
            f"{cv_results['test_precision'][i]:<12.4f} "
            f"{cv_results['test_recall'][i]:<10.4f} "
            f"{cv_results['test_f1'][i]:<10.4f} "
            f"{cv_results['test_accuracy'][i]:<10.4f}"
        )

    # Aggregate metrics
    metrics = {
        "auc_roc": {
            "mean": float(np.mean(cv_results["test_auc_roc"])),
            "std": float(np.std(cv_results["test_auc_roc"])),
        },
        "precision": {
            "mean": float(np.mean(cv_results["test_precision"])),
            "std": float(np.std(cv_results["test_precision"])),
        },
        "recall": {
            "mean": float(np.mean(cv_results["test_recall"])),
            "std": float(np.std(cv_results["test_recall"])),
        },
        "f1": {
            "mean": float(np.mean(cv_results["test_f1"])),
            "std": float(np.std(cv_results["test_f1"])),
        },
        "accuracy": {
            "mean": float(np.mean(cv_results["test_accuracy"])),
            "std": float(np.std(cv_results["test_accuracy"])),
        },
    }

    print(f"\n   📈 Mean AUC-ROC: {metrics['auc_roc']['mean']:.4f} ± {metrics['auc_roc']['std']:.4f}")
    print(f"   📈 Mean Precision: {metrics['precision']['mean']:.4f} ± {metrics['precision']['std']:.4f}")
    print(f"   📈 Mean Recall: {metrics['recall']['mean']:.4f} ± {metrics['recall']['std']:.4f}")
    print(f"   📈 Mean F1: {metrics['f1']['mean']:.4f} ± {metrics['f1']['std']:.4f}")

    # -------------------------------------------------------------------------
    # Step 4: Train Final Model on Full Dataset
    # -------------------------------------------------------------------------
    print("\n🏋️ Step 4: Training final model on full dataset...")

    # Scale features for the final model
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X.values)

    final_model = GradientBoostingClassifier(**MODEL_PARAMS)
    final_model.fit(X_scaled, y)

    # Full dataset metrics
    y_pred = final_model.predict(X_scaled)
    y_pred_proba = final_model.predict_proba(X_scaled)[:, 1]

    full_auc = roc_auc_score(y, y_pred_proba)
    print(f"   Full dataset AUC-ROC: {full_auc:.4f}")

    print("\n   Classification Report:")
    report = classification_report(y, y_pred, target_names=["Success", "Failed"])
    print("   " + report.replace("\n", "\n   "))

    cm = confusion_matrix(y, y_pred)
    print(f"   Confusion Matrix:")
    print(f"   [[TN={cm[0][0]}, FP={cm[0][1]}],")
    print(f"    [FN={cm[1][0]}, TP={cm[1][1]}]]")

    # -------------------------------------------------------------------------
    # Step 5: Feature Importance
    # -------------------------------------------------------------------------
    print("\n🔍 Step 5: Feature Importance Ranking:")

    importances = final_model.feature_importances_
    importance_df = pd.DataFrame({
        "Feature": feature_names,
        "Importance": importances,
    }).sort_values("Importance", ascending=False)

    for _, row in importance_df.iterrows():
        bar = "█" * int(row["Importance"] * 100)
        print(f"   {row['Feature']:<25} {row['Importance']:.4f} {bar}")

    metrics["feature_importance"] = dict(
        zip(importance_df["Feature"], importance_df["Importance"].round(6))
    )

    # -------------------------------------------------------------------------
    # Step 6: Save Artifacts
    # -------------------------------------------------------------------------
    print("\n💾 Step 6: Saving model artifacts...")

    joblib.dump(final_model, MODEL_OUTPUT_PATH)
    print(f"   Model saved: {MODEL_OUTPUT_PATH}")

    joblib.dump(scaler, SCALER_OUTPUT_PATH)
    print(f"   Scaler saved: {SCALER_OUTPUT_PATH}")

    # Add metadata to metrics
    metrics["model_params"] = MODEL_PARAMS
    metrics["training_samples"] = TRAINING_SAMPLES
    metrics["n_features"] = len(feature_names)
    metrics["feature_names"] = feature_names
    metrics["trained_at"] = datetime.now().isoformat()
    metrics["full_dataset_auc_roc"] = float(full_auc)

    with open(METRICS_OUTPUT_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"   Metrics saved: {METRICS_OUTPUT_PATH}")

    print("\n" + "=" * 60)
    print("✅ Training complete!")
    print("=" * 60)

    return metrics


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    metrics = train_model()
