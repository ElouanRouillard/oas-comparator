import argparse
import json
import subprocess
import sys
from pathlib import Path

from deepdiff import DeepDiff
import yaml

from src.analyzer import analyze_diff, extract_metrics, extract_top_differences, load_oas_spec

CONFIG_PATH = Path("config.yaml")




def load_configuration() -> dict:
    """
    Loads the YAML configuration file if present, otherwise returns default settings.

    Args:
        None (reads configuration from the CONFIG_PATH file if it exists).

    Returns:
        dict: A dictionary containing operational parameters such as:
            - 'default_output_dir' (str): Target directory for CLI outputs.
            - 'cache_file' (str): Path to the temporary cache file used by Streamlit.
            - 'stdout' (bool): Flag indicating whether to output JSON to stdout.
            - 'ui' (bool): Flag indicating whether to launch the Streamlit interface.
    """
    defaults = {
        "default_output_dir": "output",
        "cache_file": ".cache/temp_data.json",
        "stdout": False,
        "ui": False,
    }

    if not CONFIG_PATH.exists():
        return defaults

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
            return {
                "default_output_dir": user_config.get("default_output_dir", defaults["default_output_dir"]),
                "cache_file": user_config.get("cache_file", defaults["cache_file"]),
                "stdout": user_config.get("cli", {}).get("stdout", defaults["stdout"]),
                "ui": user_config.get("cli", {}).get("ui", defaults["ui"]),
            }
    except Exception as e:
        print(f"Warning: Unable to read {CONFIG_PATH} ({e}). Using default values.",file=sys.stderr,)
        return defaults







def analyze_files(path_a: Path, path_b: Path) -> dict:
    """
    Executes the comparative analysis between two OpenAPI specification files.

    Loads both files, computes raw differences using DeepDiff, formats the structural diff, 
    and extracts metrics for the visual dashboard.

    Args:
        path_a (Path): File path to the first OpenAPI/Swagger document (JSON or YAML).
        path_b (Path): File path to the second OpenAPI/Swagger document (JSON or YAML).

    Returns:
        dict: A payload dictionary structured as follows:
            - 'data_json' (dict): Structured additions, deletions, and modifications.
            - 'info_dashboard' (dict): Comparative metrics (coverage, endpoints) and top differences.
            - 'file_a_name' (str): Filename of the first document.
            - 'file_b_name' (str): Filename of the second document.
    """
    doc_a = load_oas_spec(path_a)
    doc_b = load_oas_spec(path_b)

    raw_diff = DeepDiff(doc_a, doc_b, ignore_order=True)
    analysis_result = analyze_diff(raw_diff, doc_a, doc_b)

    dashboard_info = {
        "doc_a_metrics": extract_metrics(doc_a),
        "doc_b_metrics": extract_metrics(doc_b),
        "top_3": extract_top_differences(analysis_result, doc_a_name=path_a.name, doc_b_name=path_b.name, limit=3),
    }

    return {
        "data_json": analysis_result,
        "info_dashboard": dashboard_info,
        "doc_a_name": path_a.name,
        "doc_b_name": path_b.name,
    }






def main():
    """
    Main CLI entry point for the OpenAPI Comparator application.

    Parses command-line arguments, evaluates configuration settings, and handles three execution modes:
    1. UI-only Server Mode: Launches Streamlit directly for browser uploads.
    2. CLI + UI Mode: Analyzes provided files, writes cache, and launches Streamlit dashboard.
    3. Pure CLI Mode: Analyzes provided files and outputs JSON to a file or standard output (stdout).

    Args:
        None (parses arguments directly from sys.argv using argparse).

    Returns:
        None
    """
    config = load_configuration()

    parser = argparse.ArgumentParser(description="OpenAPI (OAS) comparative analysis tool.")
    parser.add_argument("doc_a",nargs="?",type=Path,help="Path to the first OAS file (JSON or YAML)")
    parser.add_argument("doc_b",nargs="?",type=Path,help="Path to the second OAS file (JSON or YAML)")
    parser.add_argument("-o","--output",type=Path,help="Destination path to save the output JSON file")
    parser.add_argument("--stdout",action="store_true",help="[CLI Only] Print JSON output directly to console")
    parser.add_argument("--ui", action="store_true", help="Launch the Streamlit interface")

    args = parser.parse_args()

    launch_ui = args.ui or config["ui"]
    use_stdout = args.stdout or (config["stdout"] and not launch_ui)

    if launch_ui and args.stdout:
        parser.error("The --stdout option cannot be used alongside the --ui interface.")

    cache_path = Path(config["cache_file"])

    # =========================================================================
    # CASE 1: Pure UI Server (--ui without files)
    # =========================================================================
    if launch_ui and not args.doc_a and not args.doc_b:
        if cache_path.exists():
            cache_path.unlink()
        print("Starting Streamlit server in remote mode...", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/streamlit_app.py", "--", "--server-mode"])
        return

    if not args.doc_a or not args.doc_b:
        parser.error("Please provide two OAS files to compare (doc_a and doc_b).")

    if not args.doc_a.exists() or not args.doc_b.exists():
        print("Error: One of the input files does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        payload = analyze_files(args.doc_a, args.doc_b)
    except ValueError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # =========================================================================
    # CASE 2: Analysis with UI (doc_a + doc_b + --ui)
    # =========================================================================
    if launch_ui and args.doc_a and args.doc_b:
        default_filename = f"diff_{args.doc_a.stem}_vs_{args.doc_b.stem}.json"
        target_output = args.output
        
        if not target_output:
            out_dir = Path(config["default_output_dir"])
            target_output = out_dir / default_filename
        elif target_output.is_dir() or str(target_output).endswith(('/', '\\')):
            target_output = target_output / default_filename
            
        target_output.parent.mkdir(parents=True, exist_ok=True)
        with target_output.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
        print(f"Report exported to: {target_output}", file=sys.stderr)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)

        print("Opening Streamlit Dashboard...", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/streamlit_app.py", "--", "--cli-mode"])
        return

    # =========================================================================
    # CASE 3: Pure CLI Mode (doc_a + doc_b without UI)
    # =========================================================================
    if not launch_ui and args.doc_a and args.doc_b:
        default_filename = f"diff_{args.doc_a.stem}_vs_{args.doc_b.stem}.json"
        if use_stdout:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
        else:
            target_output = args.output
            if not target_output:
                out_dir = Path(config["default_output_dir"])
                target_output = out_dir / default_filename
            elif target_output.is_dir() or str(target_output).endswith(('/', '\\')):
                target_output = target_output / default_filename

            target_output.parent.mkdir(parents=True, exist_ok=True)
            with target_output.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4, default=str)
            print(f"Analysis completed. Output file generated: {target_output}",file=sys.stderr,)




if __name__ == "__main__":
    main()