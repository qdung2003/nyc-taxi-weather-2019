"""Main entry point with options: --only, --list, and --all."""
from __future__ import annotations

import argparse, os, re, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from pipeline.services.paths import PROJECT_ROOT, PIPELINE_DIR
from pipeline.services.connect import DuckDBConnectionManager

SCRIPT_NAME_PATTERN = re.compile(r"^(?P<step>\d{2})_.+\.py$")

SCRIPT_DIRS = {
    ("taxi", "etl"): PIPELINE_DIR / "taxi" / "etl",
    ("taxi", "eda"): PIPELINE_DIR / "taxi" / "eda" / "scripts",
    ("weather", "etl"): PIPELINE_DIR / "weather" / "etl",
    ("weather", "eda"): PIPELINE_DIR / "weather" / "eda" / "scripts",
}

CONN_REQUIRED_SCRIPTS = {
    ("taxi", "etl"): {"02", "03", "04", "05"},
    ("taxi", "eda"): {"01", "02", "03", "05", "07", "09", "11", "13"},
    ("weather", "etl"): {"02", "03", "04"},
    ("weather", "eda"): {"01", "02", "04"},
}


def parse_only_value(parts: list[str]) -> tuple[str, str, str]:
    if len(parts) != 3:
        raise SystemExit("Invalid --only format. Use: --only <taxi|weather> <etl|eda> <NN>")
    domain, stage, step = [part.strip().lower() for part in parts]
    if domain not in {"taxi", "weather"}:
        raise SystemExit(f"Invalid domain in --only: '{domain}'. Use taxi or weather.")
    if stage not in {"etl", "eda"}:
        raise SystemExit(f"Invalid stage in --only: '{stage}'. Use etl or eda.")
    if not (len(step) == 2 and step.isdigit()):
        raise SystemExit(f"Invalid step in --only: '{step}'. Step must be 2 digits (01..99).")
    return domain, stage, step


def parse_list_value(parts: list[str]) -> tuple[str, str, str | None]:
    if len(parts) not in {2, 3}:
        raise SystemExit("Invalid --list format. Use: --list <taxi|weather> <etl|eda> [NN]")
    domain, stage = [part.strip().lower() for part in parts[:2]]
    if domain not in {"taxi", "weather"}:
        raise SystemExit(f"Invalid domain in --list: '{domain}'. Use taxi or weather.")
    if stage not in {"etl", "eda"}:
        raise SystemExit(f"Invalid stage in --list: '{stage}'. Use etl or eda.")
    start_step = None
    if len(parts) == 3:
        start_step = parts[2].strip()
        if not (len(start_step) == 2 and start_step.isdigit()):
            raise SystemExit(f"Invalid start step in --list: '{start_step}'. Step must be 2 digits (01..99).")
    return domain, stage, start_step


def get_scripts(domain: str, stage: str) -> list[tuple[str, Path]]:
    script_dir = SCRIPT_DIRS[(domain, stage)]
    if not script_dir.exists():
        raise SystemExit(f"Script directory not found: {script_dir}")
    matches: list[tuple[str, Path]] = []
    for path in script_dir.glob("*.py"):
        matched = SCRIPT_NAME_PATTERN.match(path.name)
        if matched is None:
            continue
        matches.append((matched.group("step"), path.resolve()))
    matches.sort(key=lambda row: (row[0], row[1].name.lower()))
    return matches


def resolve_only_script(domain: str, stage: str, step: str) -> Path:
    scripts = get_scripts(domain, stage)
    matched = [path for script_step, path in scripts if script_step == step]
    if not matched:
        raise SystemExit(f"No script found for --only {domain}/{stage}/{step}")
    if len(matched) > 1:
        names = ", ".join(path.name for path in matched)
        raise SystemExit(f"Ambiguous step {step} in {domain}/{stage}: {names}")
    return matched[0]


def run_script_with_conn_if_needed(domain: str, stage: str, script: Path, shared_conn=None) -> None:
    required_steps = CONN_REQUIRED_SCRIPTS.get((domain, stage), set())
    matched = SCRIPT_NAME_PATTERN.match(script.name)
    step = matched.group("step") if matched is not None else None
    
    label = f"[{domain.upper()} {stage.upper()}]"

    # Standardize module name for __import__
    if stage == "eda":
        module_name = f"pipeline.{domain}.eda.scripts.{script.stem}"
    else:
        module_name = f"pipeline.{domain}.{stage}.{script.stem}"

    try:
        if step in required_steps:
            if shared_conn:
                print(f"\n{label} >>> Running (with shared conn): {script.relative_to(PROJECT_ROOT).as_posix()}")
                module = __import__(module_name, fromlist=["main"])
                module.main(shared_conn)
            else:
                manager = DuckDBConnectionManager()
                try:
                    with manager.get_connection() as conn:
                        print(f"\n{label} >>> Running (with managed conn): {script.relative_to(PROJECT_ROOT).as_posix()}")
                        module = __import__(module_name, fromlist=["main"])
                        module.main(conn)
                finally:
                    manager.close()
        else:
            print(f"\n{label} >>> Running: {script.relative_to(PROJECT_ROOT).as_posix()}")
            module = __import__(module_name, fromlist=["main"])
            module.main()
    except Exception as e:
        print(f"\nERROR in {label} {script.name}: {e}")
    except SystemExit as e:
        if e.code != 0:
            print(f"\nERROR (SystemExit) in {label} {script.name}: code {e.code}")


def handle_only(parts: list[str]) -> None:
    domain, stage, step = parse_only_value(parts)
    script = resolve_only_script(domain, stage, step)
    run_script_with_conn_if_needed(domain, stage, script)


def handle_list(parts: list[str], shared_conn=None) -> None:
    domain, stage, start_step = parse_list_value(parts)
    scripts = get_scripts(domain, stage)
    if start_step is not None:
        scripts = [(step, path) for step, path in scripts if step >= start_step]
    if not scripts:
        if start_step is None:
            print(f"No scripts found for {domain}/{stage}.")
        else:
            print(f"No scripts found for {domain}/{stage} from step {start_step}.")
        return
    print(f"Running group {domain}/{stage}:")
    for step, path in scripts:
        run_script_with_conn_if_needed(domain, stage, path, shared_conn=shared_conn)


def run_domain_pipeline(domain: str, shared_conn) -> None:
    """Run ETL then EDA for a domain sequentially using a shared connection."""
    print(f"Starting pipeline for {domain.upper()}...")
    # ETL
    handle_list([domain, "etl"], shared_conn=shared_conn)
    # EDA
    handle_list([domain, "eda"], shared_conn=shared_conn)
    print(f"Pipeline for {domain.upper()} complete.")


def handle_all() -> None:
    print("Executing ALL flows in 2 parallel domain pipelines (Taxi & Weather)...")
    manager = DuckDBConnectionManager()
    with manager.get_connection() as shared_conn:
        with ThreadPoolExecutor(max_workers=2) as executor:
            # We use the same shared_conn because DuckDB connection objects are thread-safe.
            # This avoids file-locking issues.
            executor.map(lambda d: run_domain_pipeline(d, shared_conn), ["taxi", "weather"])
    manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pipeline scripts by domain/stage/step.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --only taxi etl 01\n"
            "  python main.py --list taxi etl\n"
            "  python main.py --list taxi eda 13\n"
            "  python main.py --all\n"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--only", nargs=3, metavar=("DOMAIN", "STAGE", "STEP"), help="Run one script: <taxi|weather> <etl|eda> <NN>.")
    group.add_argument("--list", nargs="+", metavar="ARGS", help="Run all scripts in group: <taxi|weather> <etl|eda> [NN].")
    group.add_argument("--all", action="store_true", help="Run Taxi and Weather pipelines (ETL then EDA) in parallel.")
    args = parser.parse_args()

    if args.only:
        handle_only(args.only)
        return
    if args.all:
        handle_all()
        return
    handle_list(args.list)


if __name__ == "__main__":
    main()
