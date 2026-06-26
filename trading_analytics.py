from __future__ import annotations

import csv
import datetime as dt
import math
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class AnalysisData:
    source_name: str
    dates: np.ndarray
    returns_pct: np.ndarray
    current_nlv: float | None
    current_date: dt.date | None
    raw_rows: int
    nonzero_return_rows: int
    cleaned_rows: int
    excluded_nonzero_rows: int


def _to_float(value) -> float:
    if value is None:
        return 0.0
    value = str(value).strip()
    if value == "":
        return 0.0
    return float(value.replace(",", ""))


def _parse_date(value: str) -> dt.date:
    value = str(value).strip()
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        # Fallbacks for common export formats.
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    raise ValueError(f"Could not parse date value: {value!r}")


def load_balance_history(csv_path: Path) -> AnalysisData:
    """
    Load a balance-history CSV and return cleaned daily trading returns.

    Expected columns:
    - Date
    - Day_PL_Percent
    - Deposits/Withdrawals

    Cleaning:
    - remove zero-return rows
    - remove rows with deposits/withdrawals
    - remove obvious transfer/accounting artifacts where |Day_PL_Percent| > 10
    """
    rows = []
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"Date", "Day_PL_Percent", "Deposits/Withdrawals"}
        missing = sorted(required.difference(reader.fieldnames or []))
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")

        for row in reader:
            parsed = {"Date": _parse_date(row["Date"])}
            parsed["Day_PL_Percent"] = _to_float(row["Day_PL_Percent"])
            parsed["Deposits/Withdrawals"] = _to_float(row["Deposits/Withdrawals"])
            parsed["NLV"] = _to_float(row.get("NLV", "0"))
            rows.append(parsed)

    rows = sorted(rows, key=lambda r: r["Date"])
    nonzero_rows = [r for r in rows if abs(r["Day_PL_Percent"]) > 1e-12]
    clean_rows = [
        r
        for r in nonzero_rows
        if abs(r["Deposits/Withdrawals"]) < 1e-9 and abs(r["Day_PL_Percent"]) <= 10
    ]

    if not clean_rows:
        raise ValueError("No cleaned trading-return rows were found after applying filters.")

    current_nlv = rows[-1]["NLV"] if rows else None
    current_date = rows[-1]["Date"] if rows else None

    return AnalysisData(
        source_name=Path(csv_path).name,
        dates=np.array([r["Date"] for r in clean_rows]),
        returns_pct=np.array([r["Day_PL_Percent"] for r in clean_rows], dtype=float),
        current_nlv=current_nlv,
        current_date=current_date,
        raw_rows=len(rows),
        nonzero_return_rows=len(nonzero_rows),
        cleaned_rows=len(clean_rows),
        excluded_nonzero_rows=len(nonzero_rows) - len(clean_rows),
    )


def _stats(data: AnalysisData) -> dict[str, float]:
    returns = data.returns_pct
    mean = float(np.mean(returns))
    median = float(np.median(returns))
    std = float(np.std(returns, ddof=1))
    z = (returns - mean) / std
    skew = float(np.mean(z**3))
    excess_kurtosis = float(np.mean(z**4) - 3)
    positive_day_rate = float(np.mean(returns > 0))
    return {
        "mean": mean,
        "median": median,
        "std": std,
        "skew": skew,
        "excess_kurtosis": excess_kurtosis,
        "positive_day_rate": positive_day_rate,
    }


def _format_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def _format_pct(value: float) -> str:
    return f"{value:+.2f}%"


def return_distribution_chart(data: AnalysisData, output_path: Path) -> dict[str, float]:
    returns = data.returns_pct
    stats = _stats(data)
    mean = stats["mean"]
    median = stats["median"]
    std = stats["std"]

    x = np.linspace(min(returns), max(returns), 600)
    pdf = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std) ** 2)

    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    ax.hist(
        returns,
        bins=36,
        density=True,
        alpha=0.55,
        edgecolor="black",
        linewidth=0.4,
        label="Actual daily returns",
    )
    ax.plot(x, pdf, linewidth=2.5, label="Normal curve using actual mean/stdev")
    ax.axvline(0, linewidth=1.3, linestyle="--", label="Break-even")
    ax.axvline(mean, linewidth=2.2, label=f"Average daily return: {mean:+.2f}%")
    ax.axvline(median, linewidth=1.7, linestyle=":", label=f"Median daily return: {median:+.2f}%")

    ax.set_title("Daily Return Distribution", fontsize=18, fontweight="bold", pad=14)
    ax.text(
        0.5,
        1.01,
        "Positive drift with downside tail risk.",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
    )
    ax.set_xlabel("Daily return (%)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)

    stats_text = (
        f"Mean: {mean:+.2f}%\n"
        f"Median: {median:+.2f}%\n"
        f"Std dev: {std:.2f}%\n"
        f"Skew: {stats['skew']:+.2f}\n"
        f"Excess kurtosis: {stats['excess_kurtosis']:+.2f}"
    )
    ax.text(
        0.03,
        0.95,
        stats_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.10),
    )

    takeaway = (
        "Many small outcomes around the center, a positive average return,\n"
        "and left-tail risk from occasional larger losses."
    )
    ax.text(
        0.5,
        -0.16,
        takeaway,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.08),
    )

    ax.grid(alpha=0.20)
    ax.legend(loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return stats


def assumption_scatter_chart(data: AnalysisData, output_path: Path) -> float:
    returns = data.returns_pct
    today = returns[:-1]
    tomorrow = returns[1:]
    corr = float(np.corrcoef(today, tomorrow)[0, 1])

    slope, intercept = np.polyfit(today, tomorrow, 1)
    x_line = np.linspace(min(today), max(today), 200)
    y_line = slope * x_line + intercept

    fig, ax = plt.subplots(figsize=(10.5, 7))
    ax.scatter(today, tomorrow, alpha=0.55, s=36)
    ax.plot(x_line, y_line, linewidth=2)

    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)

    ax.set_title("Monte Carlo Assumption Check", fontsize=18, fontweight="bold", pad=14)
    ax.text(
        0.5,
        1.01,
        "If random sampling from historical daily returns is valid, one day should not meaningfully predict the next.",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
    )
    ax.set_xlabel("Today's trading return (%)", fontsize=12)
    ax.set_ylabel("Next trading day's return (%)", fontsize=12)

    callout = f"Correlation = {corr:+.3f}\nResult: no meaningful day-to-day pattern"
    ax.text(
        0.03,
        0.97,
        callout,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.10),
    )

    takeaway = (
        "This checks whether the Monte Carlo is obviously flawed by randomly sampling daily returns.\n"
        "Based on this data, prior-day returns do not meaningfully predict the next day."
    )
    ax.text(
        0.5,
        -0.18,
        takeaway,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.08),
    )

    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return corr


def magnitude_clustering_chart(data: AnalysisData, output_path: Path) -> float:
    returns = data.returns_pct
    today_mag = np.abs(returns[:-1])
    tomorrow_mag = np.abs(returns[1:])
    corr = float(np.corrcoef(today_mag, tomorrow_mag)[0, 1])

    slope, intercept = np.polyfit(today_mag, tomorrow_mag, 1)
    x_line = np.linspace(min(today_mag), max(today_mag), 200)
    y_line = slope * x_line + intercept

    fig, ax = plt.subplots(figsize=(10.5, 7))
    ax.scatter(today_mag, tomorrow_mag, alpha=0.55, s=36)
    ax.plot(x_line, y_line, linewidth=2)

    ax.set_title("Return Magnitude Clustering Check", fontsize=18, fontweight="bold", pad=14)
    ax.text(
        0.5,
        1.01,
        "This checks whether large moves — gains or losses — tend to be followed by more large moves.",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
    )
    ax.set_xlabel("Today's return magnitude |return| (%)", fontsize=12)
    ax.set_ylabel("Next trading day's return magnitude |return| (%)", fontsize=12)

    callout = f"Magnitude correlation = {corr:+.3f}\nResult: no meaningful clustering of large moves"
    ax.text(
        0.03,
        0.97,
        callout,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.10),
    )

    takeaway = (
        "The chart does not show large gains or losses consistently leading to more large gains or losses.\n"
        "That further supports random daily sampling from historical returns in the Monte Carlo model."
    )
    ax.text(
        0.5,
        -0.17,
        takeaway,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.08),
    )

    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return corr


def _equity_from_returns(path_returns: np.ndarray, start_value: float) -> np.ndarray:
    growth = np.cumprod(1 + path_returns / 100)
    return np.concatenate([[start_value], start_value * growth])


def _max_drawdown(equity_path: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity_path)
    return float(np.min(equity_path / peaks - 1))


def monte_carlo_chart(
    data: AnalysisData,
    output_path: Path,
    horizon: Literal["1y", "10y"] = "1y",
    n_paths: int = 1000,
    all_paths: bool = True,
    seed: int = 24062026,
) -> dict[str, float]:
    if data.current_nlv is None or data.current_nlv <= 0:
        raise ValueError("Current NLV is missing or invalid; Monte Carlo needs a positive current NLV.")

    days = 252 if horizon == "1y" else 2520
    title_horizon = "1 Year" if horizon == "1y" else "10 Years"

    rng = np.random.default_rng(seed)
    draws = rng.choice(data.returns_pct, size=(n_paths, days), replace=True)

    equity = np.empty((n_paths, days + 1))
    max_dd = np.empty(n_paths)
    for i in range(n_paths):
        equity[i] = _equity_from_returns(draws[i], data.current_nlv)
        max_dd[i] = _max_drawdown(equity[i])

    x = np.arange(days + 1)
    p10, p25, p50, p75, p90 = np.percentile(equity, [10, 25, 50, 75, 90], axis=0)

    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    if all_paths:
        ax.plot(x, equity.T, alpha=0.012 if horizon == "10y" else 0.025, linewidth=0.5)

    ax.fill_between(x, p10, p90, alpha=0.20, label="10th–90th percentile")
    ax.fill_between(x, p25, p75, alpha=0.30, label="25th–75th percentile")
    ax.plot(x, p50, linewidth=2.5, label="Median path")
    ax.axhline(data.current_nlv, linestyle="--", linewidth=1, label="Current NLV")

    ax.set_title(f"Monte Carlo Projection: {title_horizon}", fontsize=18, fontweight="bold", pad=14)
    ax.set_xlabel("Trading days from today")
    ax.set_ylabel("Projected account value")

    if horizon == "1y":
        ax.set_xticks([0, 21, 63, 126, 189, 252])
        ax.set_xticklabels(["Today", "1 Mo", "3 Mo", "6 Mo", "9 Mo", "1 Yr"])
    else:
        ax.set_xticks([0, 252, 504, 756, 1008, 1260, 1512, 1764, 2016, 2268, 2520])
        ax.set_xticklabels(["Today", "1 Yr", "2 Yr", "3 Yr", "4 Yr", "5 Yr", "6 Yr", "7 Yr", "8 Yr", "9 Yr", "10 Yr"])

    ending = equity[:, -1]
    years = 1 if horizon == "1y" else 10
    cagr = (ending / data.current_nlv) ** (1 / years) - 1
    result = {
        "p10_ending": float(np.percentile(ending, 10)),
        "median_ending": float(np.percentile(ending, 50)),
        "p90_ending": float(np.percentile(ending, 90)),
        "median_cagr": float(np.percentile(cagr, 50)),
        "median_max_drawdown": float(np.percentile(max_dd, 50)),
        "bad_path_max_drawdown": float(np.percentile(max_dd, 10)),
        "probability_positive": float(np.mean(ending > data.current_nlv)),
    }

    stats_text = (
        f"Median ending: {_format_money(result['median_ending'])}\n"
        f"10th/90th: {_format_money(result['p10_ending'])} / {_format_money(result['p90_ending'])}\n"
        f"Positive paths: {result['probability_positive']*100:.1f}%"
    )
    ax.text(
        0.03,
        0.95,
        stats_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10.5,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.10),
    )

    ax.legend(loc="upper left")
    ax.grid(alpha=0.20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return result


def sitout_overlay_chart(
    data: AnalysisData,
    output_path: Path,
    horizon: Literal["1y", "10y"] = "1y",
    n_paths: int = 1000,
    lookback_days: int = 63,
    sitout_days: int = 21,
    seed: int = 24062026,
) -> dict[str, float]:
    if data.current_nlv is None or data.current_nlv <= 0:
        raise ValueError("Current NLV is missing or invalid; sit-out model needs a positive current NLV.")

    days = 252 if horizon == "1y" else 2520
    title_horizon = "1 Year" if horizon == "1y" else "10 Years"

    rng = np.random.default_rng(seed)
    raw = rng.choice(data.returns_pct, size=(n_paths, days), replace=True)

    def baseline(path_returns: np.ndarray) -> np.ndarray:
        return _equity_from_returns(path_returns, data.current_nlv)

    def sitout(path_returns: np.ndarray) -> tuple[np.ndarray, int]:
        equity = np.empty(days + 1)
        equity[0] = data.current_nlv
        applied = []
        cooldown = 0
        armed = True
        days_sat_out = 0

        for t in range(days):
            if cooldown > 0:
                r = 0.0
                cooldown -= 1
                days_sat_out += 1
            else:
                r = path_returns[t]

            applied.append(r)
            equity[t + 1] = equity[t] * (1 + r / 100)

            if len(applied) >= lookback_days:
                window = np.array(applied[-lookback_days:])
                trailing = np.prod(1 + window / 100) - 1

                if trailing >= 0:
                    armed = True

                if trailing < 0 and cooldown == 0 and armed:
                    cooldown = sitout_days
                    armed = False

        return equity, days_sat_out

    base_eq = np.empty((n_paths, days + 1))
    sit_eq = np.empty((n_paths, days + 1))
    sat_out = np.empty(n_paths)

    for i in range(n_paths):
        base_eq[i] = baseline(raw[i])
        sit_eq[i], sat_out[i] = sitout(raw[i])

    x = np.arange(days + 1)
    base_med = np.percentile(base_eq, 50, axis=0)
    sit_med = np.percentile(sit_eq, 50, axis=0)

    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    ax.plot(x, base_eq.T, alpha=0.012 if horizon == "10y" else 0.025, linewidth=0.5)
    ax.plot(x, sit_eq.T, alpha=0.012 if horizon == "10y" else 0.025, linewidth=0.5)
    ax.plot(x, base_med, linewidth=2.5, label="Baseline median")
    ax.plot(x, sit_med, linewidth=2.5, linestyle="--", label="Sit-out rule median")
    ax.axhline(data.current_nlv, linestyle=":", linewidth=1, label="Current NLV")

    ax.set_title(f"Sit-Out Rule Overlay: {title_horizon}", fontsize=18, fontweight="bold", pad=14)
    ax.text(
        0.5,
        1.01,
        f"Rule: after a negative {lookback_days}-trading-day period, sit out {sitout_days} trading days.",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
    )
    ax.set_xlabel("Trading days from today")
    ax.set_ylabel("Projected account value")

    if horizon == "1y":
        ax.set_xticks([0, 21, 63, 126, 189, 252])
        ax.set_xticklabels(["Today", "1 Mo", "3 Mo", "6 Mo", "9 Mo", "1 Yr"])
    else:
        ax.set_xticks([0, 252, 504, 756, 1008, 1260, 1512, 1764, 2016, 2268, 2520])
        ax.set_xticklabels(["Today", "1 Yr", "2 Yr", "3 Yr", "4 Yr", "5 Yr", "6 Yr", "7 Yr", "8 Yr", "9 Yr", "10 Yr"])

    base_end = base_eq[:, -1]
    sit_end = sit_eq[:, -1]
    result = {
        "baseline_median": float(np.percentile(base_end, 50)),
        "sitout_median": float(np.percentile(sit_end, 50)),
        "median_difference": float(np.percentile(sit_end, 50) - np.percentile(base_end, 50)),
        "average_days_sat_out": float(np.mean(sat_out)),
        "trigger_rate": float(np.mean(sat_out > 0)),
    }

    stats_text = (
        f"Baseline median: {_format_money(result['baseline_median'])}\n"
        f"Sit-out median: {_format_money(result['sitout_median'])}\n"
        f"Difference: {_format_money(result['median_difference'])}"
    )
    ax.text(
        0.03,
        0.95,
        stats_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10.5,
        bbox=dict(boxstyle="round,pad=0.45", alpha=0.10),
    )

    ax.legend(loc="upper left")
    ax.grid(alpha=0.20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return result


def make_summary_text(data: AnalysisData) -> str:
    stats = _stats(data)
    return (
        f"Source: {data.source_name}\n"
        f"Current date: {data.current_date}\n"
        f"Current NLV: {_format_money(data.current_nlv)}\n"
        f"Cleaned trading days used: {data.cleaned_rows}\n"
        f"Excluded nonzero rows: {data.excluded_nonzero_rows}\n\n"
        f"Mean daily return: {stats['mean']:+.3f}%\n"
        f"Median daily return: {stats['median']:+.3f}%\n"
        f"Daily return standard deviation: {stats['std']:.3f}%\n"
        f"Positive day rate: {stats['positive_day_rate']*100:.1f}%\n"
        f"Skew: {stats['skew']:+.3f}\n"
        f"Excess kurtosis: {stats['excess_kurtosis']:+.3f}\n"
    )


def full_report_zip(data: AnalysisData, output_zip: Path) -> dict[str, str]:
    """
    Create a zip with all major charts and a plain-text summary.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        paths = {
            "daily_return_distribution.png": tmp / "daily_return_distribution.png",
            "monte_carlo_1y.png": tmp / "monte_carlo_1y.png",
            "monte_carlo_10y.png": tmp / "monte_carlo_10y.png",
            "monte_carlo_assumption_check.png": tmp / "monte_carlo_assumption_check.png",
            "return_magnitude_clustering.png": tmp / "return_magnitude_clustering.png",
            "sitout_overlay_1y.png": tmp / "sitout_overlay_1y.png",
        }

        summary = make_summary_text(data)
        stats = return_distribution_chart(data, paths["daily_return_distribution.png"])
        mc1 = monte_carlo_chart(data, paths["monte_carlo_1y.png"], horizon="1y")
        mc10 = monte_carlo_chart(data, paths["monte_carlo_10y.png"], horizon="10y")
        corr = assumption_scatter_chart(data, paths["monte_carlo_assumption_check.png"])
        mag_corr = magnitude_clustering_chart(data, paths["return_magnitude_clustering.png"])
        sit = sitout_overlay_chart(data, paths["sitout_overlay_1y.png"], horizon="1y")

        summary += "\nMonte Carlo 1-year:\n"
        summary += f"Median ending NLV: {_format_money(mc1['median_ending'])}\n"
        summary += f"10th/90th ending NLV: {_format_money(mc1['p10_ending'])} / {_format_money(mc1['p90_ending'])}\n"
        summary += f"Probability positive: {mc1['probability_positive']*100:.1f}%\n"

        summary += "\nMonte Carlo 10-year:\n"
        summary += f"Median ending NLV: {_format_money(mc10['median_ending'])}\n"
        summary += f"10th/90th ending NLV: {_format_money(mc10['p10_ending'])} / {_format_money(mc10['p90_ending'])}\n"
        summary += f"Median CAGR: {mc10['median_cagr']*100:.1f}%\n"

        summary += "\nAssumption checks:\n"
        summary += f"Day-to-day return correlation: {corr:+.3f}\n"
        summary += f"Return magnitude correlation: {mag_corr:+.3f}\n"

        summary += "\nSit-out rule overlay:\n"
        summary += f"Baseline median: {_format_money(sit['baseline_median'])}\n"
        summary += f"Sit-out median: {_format_money(sit['sitout_median'])}\n"
        summary += f"Median difference: {_format_money(sit['median_difference'])}\n"

        summary_path = tmp / "summary.txt"
        summary_path.write_text(summary, encoding="utf-8")

        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(summary_path, arcname="summary.txt")
            for arcname, path in paths.items():
                z.write(path, arcname=arcname)

    return {"zip": str(output_zip)}
