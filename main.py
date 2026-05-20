"""CLI entry point for running ETL, EDA, and dashboard tasks."""
from __future__ import annotations

import argparse
import importlib
import inspect
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable

from pipeline.constants.paths import PIPELINE_DIR, PROJECT_ROOT


DOMAINS = {"taxi", "weather"}
STAGES = {"etl", "eda"}
SCRIPT_NAME_PATTERN = re.compile(r"^(?P<step>\d{2})_.+\.py$")

SCRIPT_DIRS = {
    ("taxi", "etl"): PIPELINE_DIR / "taxi" / "etl",
    ("taxi", "eda"): PIPELINE_DIR / "taxi" / "eda" / "scripts",
    ("weather", "etl"): PIPELINE_DIR / "weather" / "etl",
    ("weather", "eda"): PIPELINE_DIR / "weather" / "eda" / "scripts",
}


# ===== Validation =====
def validate_domain(domain: str, option_name: str) -> str:
    domain = domain.strip().lower()
    if domain not in DOMAINS:
        raise SystemExit(f"Invalid domain in {option_name}: '{domain}'. Use taxi or weather.")
    return domain


def validate_stage(stage: str, option_name: str) -> str:
    stage = stage.strip().lower()
    if stage not in STAGES:
        raise SystemExit(f"Invalid stage in {option_name}: '{stage}'. Use etl or eda.")
    return stage


def validate_step(step: str, label: str = "step") -> str:
    step = step.strip()
    if not (len(step) == 2 and step.isdigit()):
        raise SystemExit(f"Invalid {label}: '{step}'. Step must be 2 digits (01..99).")
    return step


def parse_only_value(parts: list[str]) -> tuple[str, str, list[str]]:
    if len(parts) < 3:
        raise SystemExit("Invalid --only format. Use: --only <taxi|weather> <etl|eda> <NN> [NN ...]")

    domain = validate_domain(parts[0], "--only")
    stage = validate_stage(parts[1], "--only")
    steps = [validate_step(step) for step in parts[2:]]
    return domain, stage, steps


def parse_list_value(parts: list[str]) -> tuple[str, str, str | None]:
    if len(parts) not in {2, 3}:
        raise SystemExit("Invalid --list format. Use: --list <taxi|weather> <etl|eda> [NN]")

    domain = validate_domain(parts[0], "--list")
    stage = validate_stage(parts[1], "--list")
    start_step = validate_step(parts[2], "start step in --list") if len(parts) == 3 else None
    return domain, stage, start_step


# ===== Script Discovery =====
def get_scripts(domain: str, stage: str) -> list[tuple[str, Path]]:
    script_dir = SCRIPT_DIRS[(domain, stage)]
    if not script_dir.exists():
        raise SystemExit(f"Script directory not found: {script_dir}")

    scripts: list[tuple[str, Path]] = []
    for path in script_dir.glob("*.py"):
        matched = SCRIPT_NAME_PATTERN.match(path.name)
        if matched is not None:
            scripts.append((matched.group("step"), path.resolve()))

    return sorted(scripts, key=lambda row: (row[0], row[1].name.lower()))


def resolve_only_script(domain: str, stage: str, step: str) -> Path:
    matched = [path for script_step, path in get_scripts(domain, stage) if script_step == step]
    if not matched:
        raise SystemExit(f"No script found for --only {domain}/{stage}/{step}")
    if len(matched) > 1:
        names = ", ".join(path.name for path in matched)
        raise SystemExit(f"Ambiguous step {step} in {domain}/{stage}: {names}")
    return matched[0]


def module_name_for_script(domain: str, stage: str, script: Path) -> str:
    if stage == "eda":
        return f"pipeline.{domain}.eda.scripts.{script.stem}"
    return f"pipeline.{domain}.{stage}.{script.stem}"


# ===== Execution =====
def get_connection_manager_cls():
    from pipeline.services.connect import DuckDBConnectionManager

    return DuckDBConnectionManager


def script_label(domain: str, stage: str) -> str:
    return f"[{domain.upper()} {stage.upper()}]"


def relative_script_path(script: Path) -> str:
    return script.relative_to(PROJECT_ROOT).as_posix()


def run_script_with_conn_if_needed(domain: str, stage: str, script: Path, shared_conn=None) -> None:
    label = script_label(domain, stage)
    module_name = module_name_for_script(domain, stage, script)

    try:
        module = importlib.import_module(module_name)
        main_fn = getattr(module, "main", None)
        if main_fn is None:
            raise RuntimeError(f"{module_name} has no main()")

        requires_conn = len(inspect.signature(main_fn).parameters) >= 1
        if not requires_conn:
            print(f"\n{label} >>> Running: {relative_script_path(script)}")
            main_fn()
            return

        if shared_conn is not None:
            print(f"\n{label} >>> Running (with shared conn): {relative_script_path(script)}")
            main_fn(shared_conn)
            return

        manager = get_connection_manager_cls()()
        try:
            with manager.get_connection() as conn:
                print(f"\n{label} >>> Running (with managed conn): {relative_script_path(script)}")
                main_fn(conn)
        finally:
            manager.close()
    except SystemExit as exc:
        if exc.code != 0:
            print(f"\nERROR (SystemExit) in {label} {script.name}: code {exc.code}")
    except Exception as exc:
        print(f"\nERROR in {label} {script.name}: {exc}")


def run_scripts(domain: str, stage: str, scripts: Iterable[tuple[str, Path]], shared_conn=None) -> None:
    for _, path in scripts:
        run_script_with_conn_if_needed(domain, stage, path, shared_conn=shared_conn)


# ===== Command Handlers =====
def handle_only(parts: list[str]) -> None:
    domain, stage, steps = parse_only_value(parts)
    scripts = [(step, resolve_only_script(domain, stage, step)) for step in steps]

    if len(scripts) == 1:
        run_scripts(domain, stage, scripts)
        return

    manager = get_connection_manager_cls()()
    try:
        with manager.get_connection() as conn:
            run_scripts(domain, stage, scripts, shared_conn=conn)
    finally:
        manager.close()


def handle_list(parts: list[str], shared_conn=None) -> None:
    domain, stage, start_step = parse_list_value(parts)
    scripts = get_scripts(domain, stage)
    if start_step is not None:
        scripts = [(step, path) for step, path in scripts if step >= start_step]

    if not scripts:
        suffix = "" if start_step is None else f" from step {start_step}"
        print(f"No scripts found for {domain}/{stage}{suffix}.")
        return

    print(f"Running group {domain}/{stage}:")
    if shared_conn is not None:
        run_scripts(domain, stage, scripts, shared_conn=shared_conn)
        return

    manager = get_connection_manager_cls()()
    try:
        with manager.get_connection() as conn:
            run_scripts(domain, stage, scripts, shared_conn=conn)
    finally:
        manager.close()


def run_domain_pipeline(domain: str, shared_conn) -> None:
    """Run ETL then EDA for one domain using a shared connection."""
    print(f"Starting pipeline for {domain.upper()}...")
    handle_list([domain, "etl"], shared_conn=shared_conn)
    handle_list([domain, "eda"], shared_conn=shared_conn)
    print(f"Pipeline for {domain.upper()} complete.")


def handle_domain(domain: str) -> None:
    manager = get_connection_manager_cls()()
    try:
        with manager.get_connection() as conn:
            run_domain_pipeline(domain, conn)
    finally:
        manager.close()


def handle_all() -> None:
    print("Executing ALL flows in 2 parallel domain pipelines (Taxi & Weather)...")
    manager = get_connection_manager_cls()()
    try:
        with manager.get_connection() as shared_conn:
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(lambda domain: run_domain_pipeline(domain, shared_conn), ["taxi", "weather"]))
    finally:
        manager.close()


def handle_dashboard() -> None:
    from pipeline.dashboard.dashboard import main as dashboard_main

    dashboard_main(open_html=True)


# ===== CLI =====
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pipeline scripts by domain/stage/step.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py dashboard\n"
            "  python main.py --only taxi etl 01\n"
            "  python main.py --list taxi etl\n"
            "  python main.py --list taxi eda 01\n"
            "  python main.py --taxi\n"
            "  python main.py --weather\n"
            "  python main.py --all\n"
        ),
    )
    parser.add_argument("command", nargs="?", choices=["dashboard"], help="Run dashboard data build + open HTML.")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--only", nargs="+", metavar="ARGS", help="Run one or many scripts: <taxi|weather> <etl|eda> <NN> [NN ...].")
    group.add_argument("--list", nargs="+", metavar="ARGS", help="Run all scripts in group: <taxi|weather> <etl|eda> [NN].")
    group.add_argument("--taxi", action="store_true", help="Run Taxi ETL then Taxi EDA.")
    group.add_argument("--weather", action="store_true", help="Run Weather ETL then Weather EDA.")
    group.add_argument("--all", action="store_true", help="Run Taxi and Weather pipelines (ETL then EDA) in parallel.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "dashboard":
        handle_dashboard()
    elif args.only:
        handle_only(args.only)
    elif args.list:
        handle_list(args.list)
    elif args.taxi:
        handle_domain("taxi")
    elif args.weather:
        handle_domain("weather")
    elif args.all:
        handle_all()
    else:
        parser.error("Provide one of: dashboard, --only, --list, --taxi, --weather, or --all.")


if __name__ == "__main__":
    main()
