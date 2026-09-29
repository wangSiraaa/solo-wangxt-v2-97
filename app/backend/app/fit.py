"""Theis parameter fitting with SciPy, plus model-assumption diagnostics.

The fit solves for transmissivity T and storativity S from one observation
well at known distance and constant pumping rate. Bounds are supplied by the
user (stored in PostgreSQL) and are the only constraints on the parameters;
the diagnostics below check the *answer* against plausible aquifer ranges and
the *data* against the conceptual model, and never silently clip results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from scipy.optimize import curve_fit

from .config import settings
from .theis import theis_drawdown

# Parameter order used everywhere: [T (m^2/s), S (-)].
PARAM_NAMES = ("transmissivity_m2_s", "storativity")
LOG10_T_BOUNDS = (-12.0, 2.0)   # m^2/s, generous crustal range
LOG10_S_BOUNDS = (-9.0, -1.0)   # storativity is dimensionless, <= ~1


@dataclass
class FitResult:
    converged: bool
    message: str
    transmissivity_m2_s: float | None = None
    storativity: float | None = None
    rmse_m: float | None = None
    r_squared: float | None = None
    residual_mean_m: float | None = None
    n_points: int = 0
    # Diagnostic flags, each with severity: info | warning | error
    diagnostics: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "converged": self.converged,
            "message": self.message,
            "transmissivity_m2_s": self.transmissivity_m2_s,
            "storativity": self.storativity,
            "rmse_m": self.rmse_m,
            "r_squared": self.r_squared,
            "residual_mean_m": self.residual_mean_m,
            "n_points": self.n_points,
            "diagnostics": self.diagnostics,
        }


def _model(t_s, log10_t, log10_s, r_m, q_m3_s):
    return theis_drawdown(t_s, 10.0**log10_t, 10.0**log10_s, r_m, q_m3_s)


def fit_theis(
    t_s: Sequence[float],
    drawdown_m: Sequence[float],
    distance_m: float,
    rate_m3_s: float,
    t_bounds: tuple[float, float] | None = None,
    s_bounds: tuple[float, float] | None = None,
) -> FitResult:
    """Fit T and S to drawdown data.

    ``t_s``/``drawdown_m`` are already converted to SI and must contain only
    finite, positive-time points (missing observations are excluded before
    calling this, but are retained separately by the caller).
    """
    t = np.asarray(t_s, dtype=float)
    s = np.asarray(drawdown_m, dtype=float)
    finite = np.isfinite(t) & np.isfinite(s) & (t > 0)
    t, s = t[finite], s[finite]

    diag: list[dict] = []
    n = t.size
    if n < settings.min_points_for_fit:
        return FitResult(
            converged=False,
            message=f"有效测点仅 {n} 个，少于拟合所需的 {settings.min_points_for_fit} 个。",
            n_points=n,
            diagnostics=[
                {
                    "severity": "error",
                    "code": "TOO_FEW_POINTS",
                    "message": f"至少需要 {settings.min_points_for_fit} 个有效测点才能拟合 Theis 模型。",
                }
            ],
        )

    # Default bounds (log10 space), widened by user-supplied physical bounds.
    lo_t, hi_t = LOG10_T_BOUNDS
    lo_s, hi_s = LOG10_S_BOUNDS
    if t_bounds is not None:
        lo_t = max(lo_t, np.log10(t_bounds[0]))
        hi_t = min(hi_t, np.log10(t_bounds[1]))
    if s_bounds is not None:
        lo_s = max(lo_s, np.log10(s_bounds[0]))
        hi_s = min(hi_s, np.log10(s_bounds[1]))

    # Initial guess: midpoint of log bounds.
    p0 = [0.5 * (lo_t + hi_t), 0.5 * (lo_s + hi_s)]

    try:
        popt, _pcov = curve_fit(
            lambda tt, lt, ls: _model(tt, lt, ls, distance_m, rate_m3_s),
            t,
            s,
            p0=p0,
            bounds=([lo_t, lo_s], [hi_t, hi_s]),
            maxfev=20000,
        )
    except Exception as exc:  # noqa: BLE001
        return FitResult(
            converged=False,
            message=f"拟合失败：{exc}",
            n_points=n,
            diagnostics=[
                {"severity": "error", "code": "FIT_FAILED", "message": str(exc)}
            ],
        )

    T_fit = 10.0 ** popt[0]
    S_fit = 10.0 ** popt[1]
    pred = theis_drawdown(t, T_fit, S_fit, distance_m, rate_m3_s)
    resid = s - pred
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((s - np.mean(s)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(ss_res / n))

    result = FitResult(
        converged=True,
        message="拟合完成。",
        transmissivity_m2_s=T_fit,
        storativity=S_fit,
        rmse_m=rmse,
        r_squared=r2,
        residual_mean_m=float(np.mean(resid)),
        n_points=n,
    )
    result.diagnostics = _diagnostics(
        t, s, pred, resid, T_fit, S_fit, distance_m, rate_m3_s, (lo_t, hi_t), (lo_s, hi_s)
    )
    return result


def _diagnostics(
    t, s, pred, resid, T, S, r, q, t_log_bounds, s_log_bounds
) -> list[dict]:
    diag: list[dict] = []

    # 1. Conceptual-model limitations (always shown for v1 scope).
    diag.append(
        {
            "severity": "info",
            "code": "MODEL_SCOPE",
            "message": (
                "本首版仅适用均质、各向同性、等厚承压含水层，完整井、定流量抽水，"
                "单一观测井，且假设 Theis 解（无越流、无边界影响、无井储）。"
                "实际含水层常存在非均质性、越流补给、隔水/定水边界、井储与表皮效应、"
                "流量波动及多井干扰；若数据明显偏离这些假设，拟合参数可能失真。"
            ),
        }
    )

    # 2. Storativity plausibility for a confined aquifer.
    if S < settings.storativity_plausible_min:
        diag.append(
            {
                "severity": "warning",
                "code": "S_TOO_LOW",
                "message": (
                    f"反演贮水系数 S={S:.3e} 低于承压含水层常见下限 "
                    f"{settings.storativity_plausible_min:.0e}。"
                    "若井距/流量单位错误（例如英尺误标为米），S 会被系统性压缩，"
                    "请核对距离与流量单位。"
                ),
            }
        )
    elif S > settings.storativity_plausible_max:
        diag.append(
            {
                "severity": "warning",
                "code": "S_TOO_HIGH",
                "message": (
                    f"反演贮水系数 S={S:.3e} 高于承压含水层常见上限 "
                    f"{settings.storativity_plausible_max:.0e}，"
                    "可能为潜水含水层（给水度量级）、单位错误或存在越流。"
                ),
            }
        )

    # 3. Fit hit a parameter bound.
    if abs(np.log10(S) - s_log_bounds[0]) < 1e-6 or abs(
        np.log10(S) - s_log_bounds[1]
    ) < 1e-6:
        diag.append(
            {
                "severity": "warning",
                "code": "S_AT_BOUND",
                "message": "贮水系数拟合值位于给定边界上，结果不可靠，请放宽边界或核对数据。",
            }
        )
    if abs(np.log10(T) - t_log_bounds[0]) < 1e-6 or abs(
        np.log10(T) - t_log_bounds[1]
    ) < 1e-6:
        diag.append(
            {
                "severity": "warning",
                "code": "T_AT_BOUND",
                "message": "导水系数拟合值位于给定边界上，结果不可靠，请放宽边界或核对数据。",
            }
        )

    # 4. Drawdown should be monotonic non-decreasing in time for Theis.
    if np.any(np.diff(s) < -1e-9 * max(abs(np.max(s)), 1e-9)):
        diag.append(
            {
                "severity": "info",
                "code": "NONMONOTONIC",
                "message": (
                    "观测降深随时间出现下降（回升），Theis 模型要求降深单调不减；"
                    "可能存在流量减小、水位恢复、越流或边界效应。"
                ),
            }
        )

    # 5. Early-time residual bias: well-bore storage / skin signature.
    early = slice(0, max(3, t.size // 4))
    if resid[early].size >= 3 and np.all(resid[early] < 0):
        diag.append(
            {
                "severity": "info",
                "code": "EARLY_TIME_BIAS",
                "message": (
                    "早期测点残差系统性为负（模型降深大于实测），"
                    "可能存在井储/表皮效应，Theis 解在早期不适用。"
                ),
            }
        )

    # 6. Late-time residual bias: boundary / leakage signature.
    late = slice(max(0, 3 * t.size // 4), t.size)
    if resid[late].size >= 3 and np.all(resid[late] > 0):
        diag.append(
            {
                "severity": "info",
                "code": "LATE_TIME_BIAS",
                "message": (
                    "晚期测点残差系统性为正（模型降深小于实测），"
                    "可能存在隔水边界或越流补给，Theis 无限含水层假设在晚期不成立。"
                ),
            }
        )

    return diag
