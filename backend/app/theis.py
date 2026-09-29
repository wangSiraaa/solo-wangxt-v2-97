"""Theis (1935) confined-aquifer model and SciPy curve fitting.

Scope of this first version (assumptions that must hold):

* homogeneous, isotropic, fully confined aquifer of infinite extent;
* fully penetrating pumping well;
* constant pumping rate Q from t = 0;
* a single observation well at distance r;
* drawdown measured against an undisturbed (pre-pumping) baseline;
* no leakage, no delayed yield, no wellbore storage, no boundaries.

When the data violate these assumptions the fit still runs, but the
caller is responsible for surfacing the returned ``limitations`` to the
user.  This module performs physical interpretation only; it never emits
abstraction / extraction permits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import exp1

# Plausibility envelopes used purely for *warning* users.  They are not
# hard fit bounds (those come from the request / database row).
T_WARN_MIN, T_WARN_MAX = 1.0e-8, 1.0e2      # m^2/s
S_WARN_MIN, S_WARN_MAX = 1.0e-8, 1.0e-1     # confined storativity


def theis_w(u: np.ndarray) -> np.ndarray:
    """Theis well function W(u) = exponential integral E1(u).

    Defined via ``scipy.special.exp1``.  ``u`` must be positive; very
    small u (< 1e-300) are floored to avoid overflow of u itself while
    W(u) keeps growing logarithmically (Cooper-Jacob behaviour).
    """
    u = np.maximum(np.asarray(u, dtype=float), 1e-300)
    return exp1(u)


def theis_drawdown(
    t: np.ndarray, Q: float, r: float, T: float, S: float
) -> np.ndarray:
    """Theis drawdown s(t) in metres.

    Parameters
    ----------
    t : seconds since pump start (positive)
    Q : constant pumping rate, m^3/s
    r : observation distance, m
    T : transmissivity, m^2/s
    S : storativity, dimensionless
    """
    t = np.asarray(t, dtype=float)
    u = (r**2 * S) / (4.0 * T * np.maximum(t, 1e-300))
    return Q / (4.0 * math.pi * T) * theis_w(u)


def _cooper_jacob_initial(
    t: np.ndarray, s: np.ndarray, Q: float, r: float
) -> tuple[float, float]:
    """Initial (T, S) guess from late-time Cooper-Jacob straight line.

    For small u, W(u) ~ -0.5772 - ln(u), so s plotted against ln(t)
    is a straight line with slope m = Q / (4 pi T).
    """
    order = np.argsort(t)
    t_sorted, s_sorted = t[order], s[order]
    # Fit the latest half of the record where the Jacob approximation
    # is best; guard against tiny samples.
    k = max(3, len(t_sorted) // 2)
    slope, intercept = np.polyfit(np.log(t_sorted[-k:]), s_sorted[-k:], 1)
    T0 = Q / (4.0 * math.pi * slope) if slope > 0 else 1.0e-3
    # intercept = Q/(4 pi T) * (ln(2.25 T) - ln(r^2 S))
    # -> solve for S
    if slope > 0:
        # s = slope*(ln(2.25 T t/(r^2 S))) => at ln t = x0, s = 0:
        x0 = -intercept / slope
        t0 = math.exp(x0)  # intercept time (s) of the Jacob line
        S0 = 2.25 * T0 * t0 / r**2
        S0 = min(max(S0, 1e-9), 1e-2)
    else:
        S0 = 1e-4
    T0 = min(max(T0, 1e-8), 1e1)
    return T0, S0


@dataclass
class FitResult:
    transmissivity_m2_s: float
    storativity: float
    t_bounds: list[float]
    s_bounds: list[float]
    t_se: float
    s_se: float
    t_ci95: list[float]
    s_ci95: list[float]
    rmse_m: float
    mae_m: float
    max_abs_residual_m: float
    r_squared: float
    residual_trend_slope: float
    hit_bounds: list[str]
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def fit_theis(
    times_s: list[float | None],
    drawdowns_m: list[float | None],
    Q: float,
    r: float,
    t_bounds: tuple[float, float] = (1.0e-9, 1.0e3),
    s_bounds: tuple[float, float] = (1.0e-10, 1.0e0),
    weights: str = "log",
) -> tuple[FitResult, np.ndarray, np.ndarray, np.ndarray]:
    """Fit T and S by non-linear least squares.

    Missing points (``None`` in either array) are *preserved as missing*:
    they are excluded from the fit and returned as NaN residuals rather
    than being imputed.

    ``weights``:
      * ``"log"`` (default) — fit in log-drawdown space, giving early and
        late times comparable leverage (standard pumping-test practice);
      * ``"linear"`` — plain least squares on drawdown in metres.

    Returns ``(FitResult, t_used, s_observed_used, s_model_used)``.
    """
    t_all = np.array([np.nan if v is None else v for v in times_s], dtype=float)
    s_all = np.array(
        [np.nan if v is None else v for v in drawdowns_m], dtype=float
    )
    mask = np.isfinite(t_all) & np.isfinite(s_all) & (t_all > 0)
    if mask.sum() < 3:
        raise ValueError(
            "At least 3 valid (time, drawdown) pairs with t > 0 are required."
        )
    t = t_all[mask]
    s_obs = s_all[mask]
    if Q <= 0:
        raise ValueError("Pumping rate Q must be positive.")
    if r <= 0:
        raise ValueError("Observation distance r must be positive.")
    if np.any(s_obs < 0):
        # negative drawdown = recovery / measurement artefact relative to
        # the chosen baseline; Theis s must be non-negative.
        raise ValueError(
            "Negative drawdown values present — check the reference water "
            "level / baseline; Theis drawdown must be >= 0."
        )

    T0, S0 = _cooper_jacob_initial(t, s_obs, Q, r)
    # curve_fit bounds are inclusive; nudge the initial guess inside.
    T0 = min(max(T0, t_bounds[0] * (1 + 1e-6)), t_bounds[1] * (1 - 1e-6))
    S0 = min(max(S0, s_bounds[0] * (1 + 1e-6)), s_bounds[1] * (1 - 1e-6))

    def model(tt, logT, logS):
        return theis_drawdown(tt, Q, r, math.exp(logT), math.exp(logS))

    sigma = None
    if weights == "log":
        # sigma in linear-space curve_fit equivalent to fitting log(s):
        # minimise sum [ (s_obs - s_model)/s_obs ]^2
        sigma = np.maximum(s_obs, 1e-6)
    elif weights != "linear":
        raise ValueError("weights must be 'log' or 'linear'")

    try:
        popt, pcov = curve_fit(
            model,
            t,
            s_obs,
            p0=[math.log(T0), math.log(S0)],
            sigma=sigma,
            absolute_sigma=False,
            bounds=(
                [math.log(t_bounds[0]), math.log(s_bounds[0])],
                [math.log(t_bounds[1]), math.log(s_bounds[1])],
            ),
            maxfev=20000,
        )
    except Exception as exc:  # ValueError / RuntimeError from curve_fit
        raise ValueError(f"Theis fit did not converge: {exc}") from exc

    T_hat, S_hat = math.exp(popt[0]), math.exp(popt[1])
    s_model = model(t, *popt)
    residuals = s_obs - s_model

    # Standard errors via delta method (fit done in log space):
    # Var(T) ~ (dT/dlogT)^2 Var(logT) = T^2 Var(logT)
    perr = np.sqrt(np.diag(pcov))
    t_se, s_se = T_hat * perr[0], S_hat * perr[1]
    t_ci = [T_hat - 1.96 * t_se, T_hat + 1.96 * t_se]
    s_ci = [S_hat - 1.96 * s_se, S_hat + 1.96 * s_se]
    t_ci[0] = max(t_ci[0], t_bounds[0])
    t_ci[1] = min(t_ci[1], t_bounds[1])
    s_ci[0] = max(s_ci[0], s_bounds[0])
    s_ci[1] = min(s_ci[1], s_bounds[1])

    rmse = float(np.sqrt(np.mean(residuals**2)))
    mae = float(np.mean(np.abs(residuals)))
    max_abs = float(np.max(np.abs(residuals)))
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((s_obs - np.mean(s_obs)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # Systematic misfit: residual trend against log(time).  Slope in
    # metres per log-cycle; |slope| large relative to drawdown range is a
    # classic sign of boundary / leakage / unconfined conditions.
    trend = float(np.polyfit(np.log(t), residuals, 1)[0])
    s_range = float(np.ptp(s_obs)) or 1.0

    warnings: list[str] = []
    hit: list[str] = []
    rel = 1e-4
    if T_hat <= t_bounds[0] * (1 + rel) or T_hat >= t_bounds[1] * (1 - rel):
        hit.append("T")
        warnings.append(
            "拟合得到的导水系数 T 紧贴搜索边界，边界设置可能不合理或数据与 "
            "Theis 模型不符。"
        )
    if S_hat <= s_bounds[0] * (1 + rel) or S_hat >= s_bounds[1] * (1 - rel):
        hit.append("S")
        warnings.append(
            "拟合得到的贮水系数 S 紧贴搜索边界，边界设置可能不合理或数据与 "
            "Theis 模型不符。"
        )
    if not (S_WARN_MIN <= S_hat <= S_WARN_MAX):
        warnings.append(
            f"贮水系数 S={S_hat:.3g} 超出承压含水层常见范围 "
            f"[{S_WARN_MIN:g}, {S_WARN_MAX:g}]。请核对井距单位、流量单位与"
            "基准水位；若含水层实际为潜水或存在越流，Theis 模型不适用。"
        )
    if not (T_WARN_MIN <= T_hat <= T_WARN_MAX):
        warnings.append(
            f"导水系数 T={T_hat:.3g} m²/s 超出常见范围 "
            f"[{T_WARN_MIN:g}, {T_WARN_MAX:g}] m²/s，请核对单位与数据。"
        )
    if abs(trend) / s_range > 0.05:
        warnings.append(
            "残差随 ln(t) 存在系统性趋势（首尾偏差持续同号），常见于"
            "隔水/供水边界、越流或潜水迟后疏干，Theis 假设可能不满足。"
        )
    if math.log(t[-1] / t[0]) < math.log(10):
        warnings.append(
            "观测时间跨度不足一个数量级，参数（尤其 S）可能不可靠，"
            "建议延长抽水时间。"
        )

    limitations = [
        "模型假设：均质、各向同性、等厚、无限延伸的承压含水层；抽水井完整"
        "穿透；流量自 t=0 起恒定；单一观测井；以抽水前稳定水位为基准。",
        "忽略井损、井筒储水、越流、潜水迟后疏干及任何水力边界。",
        "单观测井条件下井距与贮水系数在公式中耦合（由 u=r²S/4Tt 可知"
        "S 与 r² 成反比）：井距取小则 S 被高估，井距取大则 S 被低估。"
        "井距单位标错（如米/英尺）无法仅靠拟合识别——只要 S 仍落在合理"
        "量级内拟合就不会报错，井距必须由现场独立核对。",
        "本结果为抽水试验参数解释，不构成任何开采许可或取水许可依据。",
    ]

    result = FitResult(
        transmissivity_m2_s=T_hat,
        storativity=S_hat,
        t_bounds=[t_bounds[0], t_bounds[1]],
        s_bounds=[s_bounds[0], s_bounds[1]],
        t_se=t_se,
        s_se=s_se,
        t_ci95=t_ci,
        s_ci95=s_ci,
        rmse_m=rmse,
        mae_m=mae,
        max_abs_residual_m=max_abs,
        r_squared=r2,
        residual_trend_slope=trend,
        hit_bounds=hit,
        warnings=warnings,
        limitations=limitations,
    )
    return result, t, s_obs, s_model
