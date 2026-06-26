from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from trading_analytics import (
    assumption_scatter_chart,
    full_report_zip,
    load_balance_history,
    magnitude_clustering_chart,
    monte_carlo_chart,
    return_distribution_chart,
    sitout_overlay_chart,
)


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Put it in .env or your hosting environment.")


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def save_attachment(attachment: discord.Attachment, folder: Path) -> Path:
    if not attachment.filename.lower().endswith(".csv"):
        raise ValueError("Please upload a CSV file.")
    target = folder / attachment.filename
    await attachment.save(target)
    return target


async def send_error(interaction: discord.Interaction, error: Exception):
    message = f"Analysis failed: {error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    try:
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {DISCORD_GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global command(s)")
    except Exception as exc:
        print(f"Command sync failed: {exc}")


def guild_only_decorator():
    if DISCORD_GUILD_ID:
        return app_commands.guilds(discord.Object(id=int(DISCORD_GUILD_ID)))
    return lambda func: func


@guild_only_decorator()
@bot.tree.command(name="return_distribution", description="Create the daily return distribution chart from a balance-history CSV.")
@app_commands.describe(csv_file="Balance-history CSV export")
async def return_distribution(interaction: discord.Interaction, csv_file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    try:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)
            chart = folder / "daily_return_distribution.png"
            stats = return_distribution_chart(data, chart)

            caption = (
                f"Daily return distribution created from **{data.cleaned_rows}** cleaned trading days.\n"
                f"Mean: **{stats['mean']:+.2f}%** | Median: **{stats['median']:+.2f}%** | "
                f"Skew: **{stats['skew']:+.2f}** | Excess kurtosis: **{stats['excess_kurtosis']:+.2f}**"
            )
            await interaction.followup.send(caption, file=discord.File(chart))
    except Exception as exc:
        await send_error(interaction, exc)


@guild_only_decorator()
@bot.tree.command(name="monte_carlo", description="Run a Monte Carlo projection from a balance-history CSV.")
@app_commands.describe(
    csv_file="Balance-history CSV export",
    horizon="Projection horizon",
    paths="Number of paths, default 1000",
    all_paths="Show all simulated paths in the background",
)
@app_commands.choices(
    horizon=[
        app_commands.Choice(name="1 year", value="1y"),
        app_commands.Choice(name="10 years", value="10y"),
    ]
)
async def monte_carlo(
    interaction: discord.Interaction,
    csv_file: discord.Attachment,
    horizon: app_commands.Choice[str],
    paths: int = 1000,
    all_paths: bool = True,
):
    await interaction.response.defer(thinking=True)

    try:
        paths = max(100, min(paths, 5000))
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)
            chart = folder / f"monte_carlo_{horizon.value}.png"
            result = monte_carlo_chart(data, chart, horizon=horizon.value, n_paths=paths, all_paths=all_paths)

            caption = (
                f"Monte Carlo projection generated using **{paths}** paths and **{data.cleaned_rows}** cleaned trading days.\n"
                f"Median ending NLV: **${result['median_ending']:,.0f}** | "
                f"10th/90th: **${result['p10_ending']:,.0f} / ${result['p90_ending']:,.0f}** | "
                f"Positive paths: **{result['probability_positive']*100:.1f}%**"
            )
            await interaction.followup.send(caption, file=discord.File(chart))
    except Exception as exc:
        await send_error(interaction, exc)


@guild_only_decorator()
@bot.tree.command(name="assumption_check", description="Check whether prior-day returns predict next-day returns.")
@app_commands.describe(csv_file="Balance-history CSV export")
async def assumption_check(interaction: discord.Interaction, csv_file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    try:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)

            chart = folder / "monte_carlo_assumption_check.png"
            corr = assumption_scatter_chart(data, chart)

            caption = (
                "Monte Carlo assumption check complete.\n"
                f"Day-to-day return correlation: **{corr:+.3f}**. "
                "If there were meaningful clustering, this chart would show a clear pattern."
            )
            await interaction.followup.send(caption, file=discord.File(chart))
    except Exception as exc:
        await send_error(interaction, exc)


@guild_only_decorator()
@bot.tree.command(name="magnitude_clustering", description="Check whether large moves tend to be followed by more large moves.")
@app_commands.describe(csv_file="Balance-history CSV export")
async def magnitude_clustering(interaction: discord.Interaction, csv_file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    try:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)

            chart = folder / "return_magnitude_clustering.png"
            corr = magnitude_clustering_chart(data, chart)

            caption = (
                "Return magnitude clustering check complete.\n"
                f"Return magnitude correlation: **{corr:+.3f}**. "
                "This tests whether large gains or losses tend to be followed by more large moves."
            )
            await interaction.followup.send(caption, file=discord.File(chart))
    except Exception as exc:
        await send_error(interaction, exc)


@guild_only_decorator()
@bot.tree.command(name="sitout_overlay", description="Compare staying in vs. sitting out after a 3-month drawdown.")
@app_commands.describe(
    csv_file="Balance-history CSV export",
    horizon="Projection horizon",
    paths="Number of paths, default 1000",
)
@app_commands.choices(
    horizon=[
        app_commands.Choice(name="1 year", value="1y"),
        app_commands.Choice(name="10 years", value="10y"),
    ]
)
async def sitout_overlay(
    interaction: discord.Interaction,
    csv_file: discord.Attachment,
    horizon: app_commands.Choice[str],
    paths: int = 1000,
):
    await interaction.response.defer(thinking=True)

    try:
        paths = max(100, min(paths, 5000))
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)

            chart = folder / f"sitout_overlay_{horizon.value}.png"
            result = sitout_overlay_chart(data, chart, horizon=horizon.value, n_paths=paths)

            caption = (
                "Sit-out overlay generated.\n"
                f"Baseline median: **${result['baseline_median']:,.0f}** | "
                f"Sit-out median: **${result['sitout_median']:,.0f}** | "
                f"Difference: **${result['median_difference']:,.0f}**"
            )
            await interaction.followup.send(caption, file=discord.File(chart))
    except Exception as exc:
        await send_error(interaction, exc)


@guild_only_decorator()
@bot.tree.command(name="full_report", description="Generate all major charts and a summary zip from a balance-history CSV.")
@app_commands.describe(csv_file="Balance-history CSV export")
async def full_report(interaction: discord.Interaction, csv_file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    try:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            csv_path = await save_attachment(csv_file, folder)
            data = load_balance_history(csv_path)

            output_zip = folder / "trading_analysis_report.zip"
            full_report_zip(data, output_zip)

            caption = (
                f"Full report created from **{data.cleaned_rows}** cleaned trading days. "
                "The zip includes the return distribution, Monte Carlo projections, assumption checks, and sit-out overlay."
            )
            await interaction.followup.send(caption, file=discord.File(output_zip))
    except Exception as exc:
        await send_error(interaction, exc)


bot.run(DISCORD_TOKEN)
