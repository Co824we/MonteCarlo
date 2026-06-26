from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from trading_analytics import (
    assumption_scatter_chart,
    full_report_zip,
    load_balance_history,
    magnitude_clustering_chart,
    monte_carlo_chart,
    return_distribution_chart,
    sitout_overlay_chart,
)

st.set_page_config(
    page_title="ALGO Edge Trading Analytics",
    page_icon="📈",
    layout="wide",
)

st.title("ALGO Edge Trading Analytics")
st.caption("Upload a balance-history CSV and generate the Monte Carlo, return-distribution, and clustering checks.")

with st.sidebar:
    st.header("Upload")
    uploaded_file = st.file_uploader("Balance-history CSV", type=["csv"])

    st.header("Monte Carlo Settings")
    paths = st.slider("Simulation paths", min_value=500, max_value=5000, value=1000, step=500)
    show_all_paths = st.checkbox("Show all simulated paths", value=True)

    st.header("Sit-Out Rule")
    st.caption("Rule: after a negative rolling 3-month period, sit out 1 month.")
    st.caption("Current version uses 63 trading days and 21 trading days.")


def save_uploaded_file(file, folder: Path) -> Path:
    target = folder / file.name
    target.write_bytes(file.getbuffer())
    return target


if uploaded_file is None:
    st.info("Upload your latest balance-history CSV to begin.")
    st.markdown(
        """
        The CSV should include these columns:

        - `Date`
        - `Day_PL_Percent`
        - `Deposits/Withdrawals`

        Optional but recommended:

        - `NLV`
        """
    )
    st.stop()


with tempfile.TemporaryDirectory() as td:
    folder = Path(td)
    csv_path = save_uploaded_file(uploaded_file, folder)

    try:
        data = load_balance_history(csv_path)
    except Exception as exc:
        st.error(f"Could not load the CSV: {exc}")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cleaned trading days", f"{data.cleaned_rows}")
    col2.metric("Excluded nonzero rows", f"{data.excluded_nonzero_rows}")
    col3.metric("Current NLV", f"${data.current_nlv:,.0f}" if data.current_nlv else "N/A")
    col4.metric("Current date", str(data.current_date) if data.current_date else "N/A")

    st.divider()

    tabs = st.tabs(
        [
            "Daily Return Distribution",
            "Monte Carlo Projections",
            "Assumption Check",
            "Magnitude Clustering",
            "Sit-Out Overlay",
            "Full Report",
        ]
    )

    with tabs[0]:
        st.subheader("Daily Return Distribution")
        chart = folder / "daily_return_distribution.png"
        stats = return_distribution_chart(data, chart)
        st.image(str(chart), use_container_width=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Mean", f"{stats['mean']:+.3f}%")
        c2.metric("Median", f"{stats['median']:+.3f}%")
        c3.metric("Std dev", f"{stats['std']:.3f}%")
        c4.metric("Skew", f"{stats['skew']:+.3f}")
        c5.metric("Excess kurtosis", f"{stats['excess_kurtosis']:+.3f}")

        st.download_button(
            "Download chart",
            data=chart.read_bytes(),
            file_name="daily_return_distribution.png",
            mime="image/png",
        )

    with tabs[1]:
        st.subheader("Monte Carlo Projections")
        st.write("Generates both the 1-year and 10-year projections from the uploaded CSV.")

        chart_1y = folder / "monte_carlo_1y.png"
        result_1y = monte_carlo_chart(
            data,
            chart_1y,
            horizon="1y",
            n_paths=paths,
            all_paths=show_all_paths,
        )

        chart_10y = folder / "monte_carlo_10y.png"
        result_10y = monte_carlo_chart(
            data,
            chart_10y,
            horizon="10y",
            n_paths=paths,
            all_paths=show_all_paths,
        )

        st.markdown("### 1-Year Projection")
        st.image(str(chart_1y), use_container_width=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median ending NLV", f"${result_1y['median_ending']:,.0f}")
        c2.metric("10th percentile", f"${result_1y['p10_ending']:,.0f}")
        c3.metric("90th percentile", f"${result_1y['p90_ending']:,.0f}")
        c4.metric("Positive paths", f"{result_1y['probability_positive']*100:.1f}%")

        st.download_button(
            "Download 1-year chart",
            data=chart_1y.read_bytes(),
            file_name="monte_carlo_1y.png",
            mime="image/png",
        )

        st.divider()

        st.markdown("### 10-Year Projection")
        st.image(str(chart_10y), use_container_width=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median ending NLV", f"${result_10y['median_ending']:,.0f}")
        c2.metric("10th percentile", f"${result_10y['p10_ending']:,.0f}")
        c3.metric("90th percentile", f"${result_10y['p90_ending']:,.0f}")
        c4.metric("Median CAGR", f"{result_10y['median_cagr']*100:.1f}%")

        st.download_button(
            "Download 10-year chart",
            data=chart_10y.read_bytes(),
            file_name="monte_carlo_10y.png",
            mime="image/png",
        )

    with tabs[2]:
        st.subheader("Monte Carlo Assumption Check")
        st.write("This checks whether one trading day's return meaningfully predicts the next trading day's return.")
        chart = folder / "monte_carlo_assumption_check.png"
        corr = assumption_scatter_chart(data, chart)
        st.image(str(chart), use_container_width=True)
        st.metric("Day-to-day return correlation", f"{corr:+.3f}")
        st.download_button(
            "Download chart",
            data=chart.read_bytes(),
            file_name="monte_carlo_assumption_check.png",
            mime="image/png",
        )

    with tabs[3]:
        st.subheader("Return Magnitude / Volatility Clustering Check")
        st.write("This checks whether large moves — gains or losses — tend to be followed by more large moves.")
        chart = folder / "return_magnitude_clustering.png"
        mag_corr = magnitude_clustering_chart(data, chart)
        st.image(str(chart), use_container_width=True)
        st.metric("Return magnitude correlation", f"{mag_corr:+.3f}")
        st.download_button(
            "Download chart",
            data=chart.read_bytes(),
            file_name="return_magnitude_clustering.png",
            mime="image/png",
        )

    with tabs[4]:
        st.subheader("Sit-Out Rule Overlay")
        st.write("Compares the baseline Monte Carlo against sitting out after a negative rolling 3-month period.")

        sitout_1y = folder / "sitout_overlay_1y.png"
        sitout_result_1y = sitout_overlay_chart(
            data,
            sitout_1y,
            horizon="1y",
            n_paths=paths,
        )

        sitout_10y = folder / "sitout_overlay_10y.png"
        sitout_result_10y = sitout_overlay_chart(
            data,
            sitout_10y,
            horizon="10y",
            n_paths=paths,
        )

        st.markdown("### 1-Year Sit-Out Overlay")
        st.image(str(sitout_1y), use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline median", f"${sitout_result_1y['baseline_median']:,.0f}")
        c2.metric("Sit-out median", f"${sitout_result_1y['sitout_median']:,.0f}")
        c3.metric("Median difference", f"${sitout_result_1y['median_difference']:,.0f}")

        st.download_button(
            "Download 1-year sit-out chart",
            data=sitout_1y.read_bytes(),
            file_name="sitout_overlay_1y.png",
            mime="image/png",
        )

        st.divider()

        st.markdown("### 10-Year Sit-Out Overlay")
        st.image(str(sitout_10y), use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline median", f"${sitout_result_10y['baseline_median']:,.0f}")
        c2.metric("Sit-out median", f"${sitout_result_10y['sitout_median']:,.0f}")
        c3.metric("Median difference", f"${sitout_result_10y['median_difference']:,.0f}")

        st.download_button(
            "Download 10-year sit-out chart",
            data=sitout_10y.read_bytes(),
            file_name="sitout_overlay_10y.png",
            mime="image/png",
        )

    with tabs[5]:
        st.subheader("Full Report")
        st.write("Generate a zip containing all major charts and a summary text file.")

        zip_path = folder / "trading_analysis_report.zip"
        full_report_zip(data, zip_path)

        st.download_button(
            "Download full report zip",
            data=zip_path.read_bytes(),
            file_name="trading_analysis_report.zip",
            mime="application/zip",
        )
