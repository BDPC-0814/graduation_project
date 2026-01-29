import os
import pandas as pd
import matplotlib.pyplot as plt


def load_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)

    # 兼容列名：你现在的列是 time,cpu,risk,interval,state
    required = {"time", "cpu", "risk", "interval", "state"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"{path} missing columns. Found={df.columns}, required={required}")

    return df


def plot_interval(df_fixed, df_havfs, out_path="experiments/interval_compare.png"):
    plt.figure()
    plt.plot(df_fixed["time"], df_fixed["interval"], label="Fixed Interval")
    plt.plot(df_havfs["time"], df_havfs["interval"], label="HAVFS Interval")
    plt.xlabel("Time (s)")
    plt.ylabel("Sampling Interval (s)")
    plt.title("Fixed vs HAVFS - Sampling Interval")
    plt.legend()
    plt.grid(True)
    plt.savefig(out_path, dpi=200)
    print(f"[OK] Saved interval plot -> {out_path}")


def plot_risk(df_fixed, df_havfs, out_path="experiments/risk_compare.png"):
    plt.figure()
    plt.plot(df_fixed["time"], df_fixed["risk"], label="Fixed Risk")
    plt.plot(df_havfs["time"], df_havfs["risk"], label="HAVFS Risk")
    plt.xlabel("Time (s)")
    plt.ylabel("Risk Score")
    plt.title("Fixed vs HAVFS - Risk")
    plt.legend()
    plt.grid(True)
    plt.savefig(out_path, dpi=200)
    print(f"[OK] Saved risk plot -> {out_path}")


def stats(df_fixed, df_havfs):
    n_fixed = len(df_fixed)
    n_havfs = len(df_havfs)

    reduction = (n_fixed - n_havfs) / n_fixed * 100 if n_fixed > 0 else 0

    print("\n========== Sampling Points Comparison ==========")
    print(f"Fixed sampling points : {n_fixed}")
    print(f"HAVFS sampling points : {n_havfs}")
    print(f"Reduction             : {reduction:.2f}% (HAVFS vs Fixed)")

    # 平均采样间隔
    avg_fixed = df_fixed["interval"].mean()
    avg_havfs = df_havfs["interval"].mean()
    print("\n========== Interval Stats ==========")
    print(f"Fixed avg interval : {avg_fixed:.2f}s")
    print(f"HAVFS avg interval : {avg_havfs:.2f}s")


def main():
    fixed_path = "experiments/fixed.csv"
    havfs_path = "experiments/havfs.csv"

    df_fixed = load_csv(fixed_path)
    df_havfs = load_csv(havfs_path)

    # 统计
    stats(df_fixed, df_havfs)

    # 画图输出目录
    os.makedirs("experiments", exist_ok=True)

    # 绘图
    plot_interval(df_fixed, df_havfs)
    plot_risk(df_fixed, df_havfs)

    print("\n[DONE] All plots and stats finished.")


if __name__ == "__main__":
    main()
