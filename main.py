"""
CLI Interface — March Madness Bracket Prediction System

Orchestrates the full pipeline: data → features → model → upsets →
equity → simulation → optimization → output.

Usage:
    python main.py --year 2026 --risk 0.5 --pool-size 1000000 --show-upsets --explain
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="March Madness Bracket Prediction System"
    )
    parser.add_argument("--year", type=int, default=2026,
                        help="Tournament year (default: 2026)")
    parser.add_argument("--risk", type=float, default=0.5,
                        help="Risk level 0.0-1.0 (default: 0.5)")
    parser.add_argument("--bracket-input", type=str,
                        default=str(BASE_DIR / "data" / "2026" / "bracket_2026.json"),
                        help="Path to bracket JSON file")
    parser.add_argument("--output", type=str, default="table",
                        choices=["table", "json", "csv"],
                        help="Output format (default: table)")
    parser.add_argument("--pool-size", type=int, default=1_000_000,
                        help="Assumed pool size for equity (default: 1M)")
    parser.add_argument("--show-upsets", action="store_true",
                        help="Show upset alerts before bracket output")
    parser.add_argument("--explain", action="store_true",
                        help="Show model benchmark and feature importance")
    parser.add_argument("--sims", type=int, default=50_000,
                        help="Number of Monte Carlo simulations (default: 50k)")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(message)s",
    )

    console.print(Panel.fit(
        "[bold bright_yellow]MARCH MADNESS AI BRACKET PREDICTOR[/]\n"
        f"[dim]Year: {args.year}  |  Risk: {args.risk}  |  "
        f"Pool: {args.pool_size:,}  |  Sims: {args.sims:,}[/]",
        border_style="bright_yellow",
    ))

    # ── Step 1: Load data ──────────────────────────────────────────
    console.print("\n[bold]Loading data...[/]", end=" ")
    from data_pipeline import run_pipeline
    hist, curr, refs, bracket = run_pipeline()
    console.print(f"[green]64 teams loaded, {len(hist)} historical games[/]")

    # ── Step 2: Load trained models ────────────────────────────────
    console.print("[bold]Loading ML models...[/]", end=" ")
    from model import load_trained_models, predict_matchup
    from features import build_matchup_features_2026, FEATURE_NAMES
    models, config = load_trained_models()
    console.print("[green]3-model ensemble loaded (XGB + LGB + NN)[/]")

    def ml_predict(team_a_row, team_b_row, round_num, sr):
        feats = build_matchup_features_2026(team_a_row, team_b_row, round_num, sr)
        return predict_matchup(models, feats.values)

    # ── Step 3: Upset detection ────────────────────────────────────
    if args.show_upsets:
        console.print("[bold]Running upset detection...[/]", end=" ")
        from upset_detector import detect_upsets
        alerts = detect_upsets(
            curr, bracket, refs["coach_results"],
            refs["seed_results"], refs["upset_seed_info"],
        )
        high_alerts = alerts[alerts["high_alert"]]
        console.print(f"[green]{len(high_alerts)} HIGH UPSET ALERTS[/]")
        _print_upset_alerts(alerts)

    # ── Step 4: Simulation ─────────────────────────────────────────
    console.print(f"[bold]Running {args.sims:,} tournament simulations...[/]", end=" ")
    from simulator import simulate_tournament
    sim_results = simulate_tournament(
        bracket=bracket, predict_fn=ml_predict, current_teams_df=curr,
        equity_df=None, n_sims=args.sims, risk=0.0,
        seed_results=refs["seed_results"],
    )
    console.print("[green]complete[/]")

    # ── Step 5: Pool equity ────────────────────────────────────────
    console.print("[bold]Computing pool equity...[/]", end=" ")
    from pool_equity import compute_all_equity, sim_results_to_win_probs
    win_probs = sim_results_to_win_probs(sim_results["team_results"])
    picks = refs["public_picks_2026"]
    equity_df = compute_all_equity(curr, picks, win_probs_by_team=win_probs)
    console.print("[green]done[/]")

    # ── Step 6: Optimize brackets ──────────────────────────────────
    from optimizer import optimize_bracket, compare_brackets, compute_public_overlap

    console.print("[bold]Generating safe bracket (risk=0.1)...[/]", end=" ")
    safe = optimize_bracket(bracket, curr, ml_predict, equity_df,
                            refs["seed_results"], risk=0.1, pool_size=args.pool_size)
    console.print("[green]done[/]")

    console.print(f"[bold]Generating equity bracket (risk={args.risk})...[/]", end=" ")
    equity = optimize_bracket(bracket, curr, ml_predict, equity_df,
                              refs["seed_results"], risk=args.risk, pool_size=args.pool_size)
    console.print("[green]done[/]")

    comparison = compare_brackets(safe, equity)

    # ── Step 7: Display results ────────────────────────────────────
    _print_simulation_summary(sim_results)
    _print_bracket_comparison(safe, equity, comparison, curr)
    _print_full_bracket(safe, equity, comparison)
    _print_anti_chalk(safe, equity)

    if args.explain:
        _print_model_benchmark(config)

    # ── Step 8: Export ─────────────────────────────────────────────
    if args.output == "json":
        _export_json(safe, equity, sim_results)
    elif args.output == "csv":
        _export_csv(safe, equity, sim_results)


# =========================================================================
# Display functions
# =========================================================================

def _print_upset_alerts(alerts):
    """Display upset alert cards."""
    console.print()
    table = Table(
        title="UPSET ALERTS — R64",
        box=box.HEAVY_HEAD,
        title_style="bold red",
        header_style="bold",
    )
    table.add_column("Score", justify="center", width=6)
    table.add_column("Matchup", width=42)
    table.add_column("Region", width=10)
    table.add_column("KP Gap", justify="right", width=8)
    table.add_column("Hist %", justify="right", width=7)
    table.add_column("Flags", width=40)

    flag_cols = [
        "rank_within_15", "tempo_mismatch_8", "favorite_fading",
        "dog_coach_above_avg", "dog_luck_negative", "style_clash_3pt",
        "hist_upset_rate_30", "elo_close", "fav_soft_losses"
    ]
    flag_short = {
        "rank_within_15": "RankClose",
        "tempo_mismatch_8": "Tempo",
        "favorite_fading": "FavFading",
        "dog_coach_above_avg": "Coach",
        "dog_luck_negative": "LuckRegr",
        "style_clash_3pt": "StyleClash",
        "hist_upset_rate_30": "HistRate",
        "elo_close": "ELOClose",
        "fav_soft_losses": "SoftLoss",
    }

    for _, row in alerts.iterrows():
        triggered = [flag_short[f] for f in flag_cols if row[f]]
        score = int(row["upset_score"])

        if score >= 3:
            style = "bold red"
            score_str = f"[red]{score}/9[/]"
        elif score >= 2:
            style = "yellow"
            score_str = f"[yellow]{score}/9[/]"
        else:
            style = "dim"
            score_str = f"[dim]{score}/9[/]"

        matchup = f"({int(row['higher_seed'])}) {row['favorite']} vs ({int(row['lower_seed'])}) {row['underdog']}"
        flags_str = ", ".join(triggered) if triggered else "—"

        table.add_row(
            score_str,
            matchup,
            row["region"],
            str(int(row["rank_gap"])),
            f"{row['hist_upset_rate']:.0%}",
            flags_str,
            style=style if score < 3 else None,
        )

    console.print(table)


def _print_simulation_summary(sim_results):
    """Display top championship contenders from simulation."""
    console.print()
    df = sim_results["team_results"]

    table = Table(
        title=f"CHAMPIONSHIP CONTENDERS — {sim_results['n_sims']:,} Simulations",
        box=box.HEAVY_HEAD,
        title_style="bold bright_yellow",
        header_style="bold",
    )
    table.add_column("Team", width=20)
    table.add_column("Seed", justify="center", width=5)
    table.add_column("Region", width=10)
    table.add_column("S16", justify="right", width=7)
    table.add_column("E8", justify="right", width=7)
    table.add_column("F4", justify="right", width=7)
    table.add_column("Champ", justify="right", width=7)

    for _, row in df.head(15).iterrows():
        champ_pct = row["champ_pct"]
        style = "bold bright_yellow" if champ_pct > 0.10 else ("bold" if champ_pct > 0.03 else "")
        table.add_row(
            row["team_name"],
            str(int(row["seed"])),
            row["region"],
            f"{row['R16_pct']:.1%}",
            f"{row['R8_pct']:.1%}",
            f"{row['R4_pct']:.1%}",
            f"{champ_pct:.1%}",
            style=style,
        )

    console.print(table)


def _print_bracket_comparison(safe, equity, comparison, curr):
    """Display side-by-side Final Four and champion comparison."""
    from optimizer import compute_public_overlap
    console.print()

    safe_overlap = compute_public_overlap(safe["picks"])
    eq_overlap = compute_public_overlap(equity["picks"])

    grid = Table(box=box.DOUBLE, title="BRACKET COMPARISON", title_style="bold bright_cyan",
                 show_header=True, header_style="bold")
    grid.add_column("", width=20)
    grid.add_column("SAFE (risk=0.1)", justify="center", width=25, style="green")
    grid.add_column(f"EQUITY (risk={equity['risk']})", justify="center", width=25, style="bright_yellow")

    # Champion
    s_champ = safe["champion"]
    e_champ = equity["champion"]
    champ_diff = " [bold red]*DIFFERS*[/]" if s_champ != e_champ else ""
    grid.add_row(
        "[bold]Champion[/]",
        f"[bold green]{s_champ}[/]",
        f"[bold bright_yellow]{e_champ}[/]{champ_diff}",
    )

    # Final Four
    for region in ["East", "South", "West", "Midwest"]:
        s_team = safe["final_four"][region]
        e_team = equity["final_four"][region]
        s_seed = int(curr[curr.team_name == s_team].iloc[0]["seed"])
        e_seed = int(curr[curr.team_name == e_team].iloc[0]["seed"])
        diff = " [red]*[/]" if s_team != e_team else ""
        grid.add_row(
            f"  {region}",
            f"({s_seed}) {s_team}",
            f"({e_seed}) {e_team}{diff}",
        )

    grid.add_row("", "", "")
    grid.add_row("Upsets picked",
                 str(safe["picks"]["is_upset"].sum()),
                 str(equity["picks"]["is_upset"].sum()))
    grid.add_row("Public overlap",
                 f"{safe_overlap:.1%}",
                 f"{eq_overlap:.1%}")
    grid.add_row("Picks differing",
                 "", f"[bold]{comparison['different_picks']}[/] of {comparison['total_games']}")

    console.print(grid)

    # Show the actual differences
    diffs = comparison["differences"]
    if len(diffs) > 0:
        console.print()
        diff_table = Table(
            title="DIFFERING PICKS — Safe vs Equity",
            box=box.SIMPLE_HEAVY,
            title_style="bold red",
            header_style="bold",
        )
        diff_table.add_column("Round", width=8)
        diff_table.add_column("Region", width=12)
        diff_table.add_column("Matchup", width=35)
        diff_table.add_column("Safe Pick", width=18, style="green")
        diff_table.add_column("Equity Pick", width=18, style="bright_yellow")

        for _, d in diffs.iterrows():
            matchup = f"{d['team_a']} vs {d['team_b']}"
            diff_table.add_row(
                f"R{int(d['round'])}",
                d["region"],
                matchup,
                d["safe_pick"],
                d["equity_pick"],
            )
        console.print(diff_table)


def _print_full_bracket(safe, equity, comparison):
    """Print complete round-by-round bracket with differences highlighted."""
    console.print()
    diff_games = set()
    for _, d in comparison["differences"].iterrows():
        diff_games.add((int(d["round"]), d["team_a"], d["team_b"]))

    round_names = {64: "ROUND OF 64", 32: "ROUND OF 32", 16: "SWEET 16",
                   8: "ELITE 8", 4: "FINAL FOUR", 2: "CHAMPIONSHIP"}

    for rd in [64, 32, 16, 8, 4, 2]:
        safe_picks = safe["picks"][safe["picks"]["round"] == rd]
        eq_picks = equity["picks"][equity["picks"]["round"] == rd]

        table = Table(
            title=round_names[rd],
            box=box.ROUNDED,
            title_style="bold",
            header_style="bold dim",
        )
        table.add_column("Region", width=12)
        table.add_column("Matchup", width=40)
        table.add_column("Safe Pick", width=18)
        table.add_column("Equity Pick", width=18)
        table.add_column("ML %", justify="right", width=7)

        for i in range(len(safe_picks)):
            sp = safe_picks.iloc[i]
            ep = eq_picks.iloc[i]
            is_diff = (rd, sp["team_a"], sp["team_b"]) in diff_games

            matchup = f"({int(sp['seed_a'])}) {sp['team_a']} vs ({int(sp['seed_b'])}) {sp['team_b']}"

            if is_diff:
                safe_style = "[green]"
                eq_style = "[bright_yellow]"
                safe_str = f"{safe_style}{sp['winner']}[/]"
                eq_str = f"{eq_style}{ep['winner']}[/] [red]*[/]"
                row_style = "on grey15"
            else:
                upset = " ^" if sp["is_upset"] else ""
                safe_str = f"{sp['winner']}{upset}"
                eq_str = f"{ep['winner']}{upset}"
                row_style = None

            table.add_row(
                sp["region"],
                matchup,
                safe_str,
                eq_str,
                f"{sp['ml_prob_a']:.0%}",
                style=row_style,
            )

        console.print(table)


def _print_anti_chalk(safe, equity):
    """Display anti-chalk rule results."""
    console.print()
    all_corrections = []
    seen = set()
    for c in safe["corrections"] + equity["corrections"]:
        key = (c["rule"], c["auto_corrected"], c["action"][:50])
        if key not in seen:
            seen.add(key)
            all_corrections.append(c)

    table = Table(
        title="ANTI-CHALK RULES",
        box=box.SIMPLE_HEAVY,
        title_style="bold",
        header_style="bold",
    )
    table.add_column("Rule", justify="center", width=6)
    table.add_column("Status", width=16)
    table.add_column("Detail", width=70)

    for c in all_corrections:
        status = "[bold red]CORRECTED[/]" if c["auto_corrected"] else "[yellow]FLAGGED[/]"
        table.add_row(
            str(c["rule"]),
            status,
            c["action"],
        )

    console.print(table)


def _print_model_benchmark(config):
    """Display model benchmark results."""
    console.print()
    benchmarks = config.get("benchmarks", {})
    if not benchmarks:
        console.print("[dim]No benchmark data available[/]")
        return

    table = Table(
        title="MODEL BENCHMARK",
        box=box.HEAVY_HEAD,
        title_style="bold",
        header_style="bold",
    )
    table.add_column("Model", width=30)
    table.add_column("Accuracy", justify="right", width=10)
    table.add_column("Log Loss", justify="right", width=10)
    table.add_column("Brier", justify="right", width=10)
    table.add_column("AUC", justify="right", width=10)

    for key in ["cv", "holdout_ensemble", "chalk", "kenpom_only", "vegas_proxy"]:
        if key in benchmarks:
            b = benchmarks[key]
            table.add_row(
                b["label"],
                f"{b['accuracy']:.4f}",
                f"{b['log_loss']:.4f}",
                f"{b['brier_score']:.4f}",
                f"{b['auc']:.4f}",
            )

    console.print(table)


# =========================================================================
# Export functions
# =========================================================================

def _export_json(safe, equity, sim_results):
    out_dir = BASE_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)

    export = {
        "safe_bracket": {
            "champion": safe["champion"],
            "final_four": safe["final_four"],
            "picks": safe["picks"].to_dict(orient="records"),
        },
        "equity_bracket": {
            "champion": equity["champion"],
            "final_four": equity["final_four"],
            "picks": equity["picks"].to_dict(orient="records"),
        },
        "simulation": {
            "n_sims": sim_results["n_sims"],
            "team_results": sim_results["team_results"].to_dict(orient="records"),
        },
    }
    path = out_dir / "bracket_2026.json"
    with open(path, "w") as f:
        json.dump(export, f, indent=2, default=str)
    console.print(f"\n[green]Exported to {path}[/]")


def _export_csv(safe, equity, sim_results):
    out_dir = BASE_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)

    safe["picks"].to_csv(out_dir / "bracket_safe.csv", index=False)
    equity["picks"].to_csv(out_dir / "bracket_equity.csv", index=False)
    sim_results["team_results"].to_csv(out_dir / "simulation_results.csv", index=False)
    console.print(f"\n[green]Exported to {out_dir}/bracket_*.csv[/]")


if __name__ == "__main__":
    main()
