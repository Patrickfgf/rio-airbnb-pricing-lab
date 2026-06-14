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
class FittedHedonic:
    """Everything needed to predict a PRICE-space point for a new listing.

    The OLS targets log(price), so a naive exp(log_pred) underestimates the mean price by the Jensen
    gap. predict_price back-transforms with Duan's smearing estimator (mean of exp(in-sample
    residuals)) — a non-parametric correction that needs no normality assumption.
    """

    params: pd.Series  # index = design column ('const' + numeric + FE), value = OLS coefficient
    encoder: OneHotEncoder  # fitted neighbourhood one-hot (handle_unknown='ignore')
    feature_cols: tuple[str, ...]  # numeric/dummy design columns, in design order
    smearing_factor: float  # mean(exp(resid)); >= 1 when residual variance > 0

    def predict_log_price(self, x_row: pd.Series, neighbourhood: str) -> float:
        xnum = np.array([float(x_row[c]) for c in self.feature_cols], dtype=float)
        fe = self.encoder.transform(pd.DataFrame({"nb": [neighbourhood]}))[0]
        design = np.concatenate([[1.0], xnum, fe])  # 'const' + numeric + FE, matching fit order
        return float(design @ self.params.to_numpy())

    def predict_price(self, x_row: pd.Series, neighbourhood: str) -> float:
        """Price-space point estimate (BRL), smearing-corrected. Feed this to recommend_price."""
        return float(np.exp(self.predict_log_price(x_row, neighbourhood)) * self.smearing_factor)


@dataclass(frozen=True)
class HedonicResult:
    coefs: pd.DataFrame  # index=feature, cols: effect, std_err, p_value, ci_low, ci_high
    adj_r2: float
    vif: pd.Series
    model_mae: float
    baseline_median_mae: float
    baseline_nb_median_mae: float
    fitted: FittedHedonic  # per-listing price prediction (price-space, smearing-corrected)


def compute_vif(X: pd.DataFrame) -> pd.Series:
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    Xc = sm.add_constant(X.astype(float), has_constant="add")
    vals = [variance_inflation_factor(Xc.to_numpy(), i) for i in range(Xc.shape[1])]
    return pd.Series(vals, index=Xc.columns).drop("const")


def fit_hedonic(X: pd.DataFrame, y: pd.Series, neighbourhood: pd.Series) -> HedonicResult:
    Xnum = X.drop(columns=[c for c in ("cap_bucket",) if c in X.columns]).astype(float)
    nb_frame = neighbourhood.rename(
        "nb"
    ).to_frame()  # canonical name regardless of caller's Series name
    enc = OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")
    fe = enc.fit_transform(nb_frame)
    fe_df = pd.DataFrame(fe, columns=enc.get_feature_names_out(), index=Xnum.index)
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

    # Duan's smearing estimator for the log->price back-transform (see FittedHedonic).
    smearing = float(np.exp(y.to_numpy() - pred).mean())
    fitted = FittedHedonic(
        params=pd.Series(model.params, index=design.columns),
        encoder=enc,
        feature_cols=tuple(Xnum.columns),
        smearing_factor=smearing,
    )
    return HedonicResult(
        coefs, float(model.rsquared_adj), compute_vif(Xnum), model_mae, base_median, base_nb, fitted
    )
