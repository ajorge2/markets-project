"""
regression.py — Layer 1: macro baseline regression

Fits: price_to_book ~ f(T10Y2Y, UMCSENT, DSPI_yoy, CPROFIT_yoy, COMPUTSA_yoy)

Steps:
  1. Build dataset via build_dataset.py
  2. Drop outlier P/B multiples (< 0 or > 5 — likely data quality issues)
  3. Drop rows with any missing macro values
  4. Run VIF analysis — drop variables with VIF > 10 iteratively
  5. Fit OLS regression on surviving variables
  6. Report: R², coefficients, p-values, VIF for final model

Run:
    python3 analysis/regression.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

import numpy as np
import pandas as pd
from pathlib import Path
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from analysis.build_dataset import build_dataset, MACRO_SIGNALS


def _vif_table(X: pd.DataFrame) -> pd.Series:
    """Compute VIF for each column in X (must not contain the intercept column)."""
    vif = pd.Series(
        [variance_inflation_factor(X.values, i) for i in range(X.shape[1])],
        index=X.columns,
        name="VIF",
    )
    return vif.sort_values(ascending=False)


def drop_high_vif(X: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
    """
    Iteratively drop the variable with highest VIF until all VIFs < threshold.
    Returns the reduced DataFrame and prints the drop log.
    """
    X = X.copy()
    while True:
        vif = _vif_table(X)
        worst = vif.idxmax()
        if vif[worst] < threshold:
            break
        print(f"  Dropping {worst} (VIF = {vif[worst]:.1f})")
        X = X.drop(columns=[worst])
    return X


HOLDOUT_START = "2020-01-01"   # COVID era holdout: tests model on new macro regime


def run_regression():
    df = build_dataset()

    if df.empty:
        sys.exit(0)

    # Build feature column names (transform suffixes applied in build_dataset)
    feature_cols = []
    for sid, transform in MACRO_SIGNALS:
        feature_cols.append(sid if transform == "level" else f"{sid}_yoy")

    print("\n--- Data prep ---")
    print(f"Deals before filtering: {len(df)}")

    # Filter unreasonable P/B multiples
    df = df[(df["price_to_book"] > 0) & (df["price_to_book"] < 5)]
    print(f"After P/B filter (0 < P/B < 5): {len(df)}")

    # Drop rows missing any macro feature
    df = df.dropna(subset=feature_cols + ["price_to_book"])
    print(f"After dropping rows with missing macro values: {len(df)}")

    # Temporal train/test split
    # Train: pre-COVID (regime the model is fit on)
    # Test:  COVID + post-COVID (new macro regime — stress-tests model stability)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    train = df[df["signal_date"] < HOLDOUT_START]
    test  = df[df["signal_date"] >= HOLDOUT_START]
    print(f"Train (pre-{HOLDOUT_START}): {len(train)} deals")
    print(f"Test  (post-{HOLDOUT_START}): {len(test)} deals")

    if len(train) < 20:
        print("\nToo few training observations — need more deal price data.")
        print("Run edgar_ingest.py to populate deal prices.")
        sys.exit(0)

    X_train = train[feature_cols]
    y_train = train["price_to_book"]

    print("\n--- VIF analysis (training set) ---")
    print("Initial VIFs:")
    print(_vif_table(X_train).to_string())
    print()

    X_final = drop_high_vif(X_train, threshold=10.0)
    surviving = list(X_final.columns)
    print(f"\nSurviving variables: {surviving}")

    print("\n--- OLS regression (training set) ---")
    X_with_const = sm.add_constant(X_final)
    model = sm.OLS(y_train, X_with_const).fit()

    print(f"\nR²:           {model.rsquared:.3f}")
    print(f"Adj. R²:      {model.rsquared_adj:.3f}")
    print(f"Observations: {int(model.nobs)}")
    print(f"F-stat p-val: {model.f_pvalue:.4f}")

    print("\nCoefficients:")
    results = pd.DataFrame({
        "coef": model.params,
        "std_err": model.bse,
        "t": model.tvalues,
        "p": model.pvalues,
    }).round(4)
    print(results.to_string())

    print("\nFinal VIFs:")
    print(_vif_table(X_final).to_string())

    # Out-of-sample validation on holdout
    if len(test) >= 5:
        X_test = sm.add_constant(test[surviving], has_constant='add')
        y_test = test["price_to_book"]
        y_pred = model.predict(X_test)
        mae = np.abs(y_test.values - y_pred.values).mean()
        rmse = np.sqrt(((y_test.values - y_pred.values) ** 2).mean())
        print(f"\n--- Holdout validation ({len(test)} deals, post-{HOLDOUT_START}) ---")
        print(f"MAE:  {mae:.3f}")
        print(f"RMSE: {rmse:.3f}")
        print(f"Avg actual P/B:    {y_test.mean():.3f}")
        print(f"Avg predicted P/B: {y_pred.mean():.3f}")
    else:
        print(f"\nToo few holdout deals ({len(test)}) for meaningful out-of-sample test.")

    _save_outputs(model, df, train, test, surviving)
    return model, df


def _save_outputs(model, df, train, test, surviving):
    out = Path(__file__).parent

    df.to_csv(out / "deals.csv", index=False)

    ci = model.conf_int()
    ci.columns = ["conf_low", "conf_high"]
    coef_df = pd.DataFrame({
        "term":    model.params.index,
        "estimate": model.params.values,
        "std_err": model.bse.values,
        "t":       model.tvalues.values,
        "p":       model.pvalues.values,
        "conf_low":  ci["conf_low"].values,
        "conf_high": ci["conf_high"].values,
    })
    coef_df.to_csv(out / "coefficients.csv", index=False)

    pd.DataFrame({
        "fitted":   model.fittedvalues.values,
        "residual": model.resid.values,
        "leverage": model.get_influence().hat_matrix_diag,
    }).to_csv(out / "residuals.csv", index=False)

    if len(test) >= 5:
        X_test = sm.add_constant(test[surviving], has_constant="add")
        pd.DataFrame({
            "signal_date": test["signal_date"].values,
            "actual":      test["price_to_book"].values,
            "predicted":   model.predict(X_test).values,
        }).to_csv(out / "holdout.csv", index=False)

    print(f"\nOutputs saved to {out}/")


if __name__ == "__main__":
    run_regression()
