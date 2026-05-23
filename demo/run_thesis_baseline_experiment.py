import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args():
    parser = argparse.ArgumentParser(description="Run fixed/threshold/trend/evolution replay experiments for thesis evaluation.")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--duration", type=float, default=110.0)
    parser.add_argument("--trace-step", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260407)
    parser.add_argument("--fixed-interval", type=float, default=5.0)
    parser.add_argument("--t-min", type=float, default=1.0)
    parser.add_argument("--t-max", type=float, default=8.0)
    parser.add_argument("--devices", default="all")
    parser.add_argument("--gpu-vendor", default="auto", choices=["auto", "nvidia", "intel"])
    parser.add_argument("--npu-backend", default="auto", choices=["auto", "ascend", "openharmony_hdc", "rockchip_sysfs"])
    return parser.parse_args()


def run_command(args: list[str]):
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT_DIR, check=True)


def main():
    args = parse_args()
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = ROOT_DIR / "experiments" / "thesis_multi_baseline" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_dir.is_absolute():
        output_dir = ROOT_DIR / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    trace_csv = output_dir / "trace.csv"
    events_csv = output_dir / "events.csv"

    run_command(
        [
            sys.executable,
            "demo/generate_replay_trace.py",
            "--output",
            str(trace_csv),
            "--events-output",
            str(events_csv),
            "--duration",
            str(args.duration),
            "--step",
            str(args.trace_step),
            "--seed",
            str(args.seed),
        ]
    )

    mode_files: dict[str, Path] = {}
    for mode in ("fixed", "threshold", "trend", "evolution"):
        metrics_csv = output_dir / f"{mode}_metrics.csv"
        events_out = output_dir / f"{mode}_events.csv"
        outbox_db = output_dir / f"{mode}_outbox.db"
        mode_files[mode] = metrics_csv

        command = [
            sys.executable,
            "demo/evolution_sampling_experiment.py",
            "--mode",
            mode,
            "--device",
            args.devices,
            "--vendor",
            args.gpu_vendor,
            "--npu-backend",
            args.npu_backend,
            "--trace-file",
            str(trace_csv),
            "--duration",
            str(args.duration),
            "--output",
            str(metrics_csv),
            "--event-output",
            str(events_out),
            "--outbox-db",
            str(outbox_db),
        ]
        if mode == "fixed":
            command.extend(["--fixed-interval", str(args.fixed_interval)])
        else:
            command.extend(["--t-min", str(args.t_min), "--t-max", str(args.t_max)])
        run_command(command)

    report_dir = output_dir / "report"
    run_command(
        [
            sys.executable,
            "demo/evaluate_thesis_baselines.py",
            "--fixed",
            str(mode_files["fixed"]),
            "--threshold",
            str(mode_files["threshold"]),
            "--trend",
            str(mode_files["trend"]),
            "--evolution",
            str(mode_files["evolution"]),
            "--ground-truth-events",
            str(events_csv),
            "--output-dir",
            str(report_dir),
        ]
    )

    pair_report_dir = output_dir / "pair_report"
    run_command(
        [
            sys.executable,
            "demo/evaluate_metrics.py",
            "--fixed",
            str(mode_files["fixed"]),
            "--evolution",
            str(mode_files["evolution"]),
            "--ground-truth-events",
            str(events_csv),
            "--output-dir",
            str(pair_report_dir),
        ]
    )
    print(f"thesis_run={output_dir}")


if __name__ == "__main__":
    main()
