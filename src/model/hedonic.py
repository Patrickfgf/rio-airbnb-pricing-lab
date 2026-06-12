"""Interpretable hedonic price model: OLS log_price ~ features + neighbourhood fixed effects.

Returns coefficients with std errors / p-values / CIs (association, NOT causation), adjusted R²,
a VIF table, and trivial baselines so the model must out-predict median-by-neighbourhood before use.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.preprocessing import OneHotEncoder


@dataclass(frozen=True)
class HedonicResult:
    coefs: pd.DataFrame  # index=feature, cols: effect, std_err, p_value, ci_low, ci_high
    adj_r2: float
    vif: pd.Series
    model_mae: float
    baseline_median_mae: float
    baseline_nb_median_mae: float


def compute_vif(X: pd.DataFrame) -> pd.Series:
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    Xc = sm.add_constant(X.astype(float), has_constant="add")
    vals = [variance_inflation_factor(Xc.to_numpy(), i) for i in range(Xc.shape[1])]
    return pd.Series(vals, index=Xc.columns).drop("const")


def fit_hedonic(X: pd.DataFrame, y: pd.Series, neighbourhood: pd.Series) -> HedonicResult:
    Xnum = X.drop(columns=[c for c in ("cap_bucket",) if c in X.columns]).astype(float)
    enc = OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")
    fe = enc.fit_transform(neighbourhood.to_frame())
    fe_df = pd.DataFrame(fe, columns=enc.get_feature_names_out(["nb"]), index=Xnum.index)
    design = sm.add_constant(pd.concat([Xnum, fe_df], axis=1), has_constant="add")

    model = sm.OLS(y.to_numpy(), design.to_numpy()).fit()
    ci = model.conf_int()
    coefs = pd.DataFrame(
        {
            "effect": model.params,
            "std_err": model.bse,
            "p_value": model.pvalues,
            "ci_low": ci[:, 0],
            "ci_high": ci[:, 1],
        },
        index=design.columns,
    ).drop("const")
    coefs = coefs.loc[~coefs.index.str.startswith("nb_")]  # hide FE nuisance rows from the table

    pred = model.predict(design.to_numpy())
    model_mae = float(np.abs(y.to_numpy() - pred).mean())
    base_median = float(np.abs(y - y.median()).mean())
    nb_med = y.groupby(neighbourhood.to_numpy()).transform("median")
    base_nb = float(np.abs(y - nb_med).mean())
    return HedonicResult(
        coefs, float(model.rsquared_adj), compute_vif(Xnum), model_mae, base_median, base_nb
    )
