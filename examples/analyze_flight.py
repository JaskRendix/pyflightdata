from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def analyze_flight_data(parquet_path: Path) -> None:
    """Load decoded flight data and generate an inspection report and plots."""
    if not parquet_path.exists():
        print(f"Error: Decoded file not found at {parquet_path}")
        print("Please run your batch processing script first to generate output files.")
        return

    print(f"Loading flight data from {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)

    # 1. Print basic dataset info & summary statistics
    print("\n--- Dataset Info ---")
    print(df.info())

    print("\n--- Unique Parameters Found ---")
    parameters = df["parameter_name"].unique()
    print(parameters)

    print("\n--- Summary Statistics ---")
    print(df.groupby("parameter_name")["value"].describe())

    # 2. Pivot the DataFrame so each parameter gets its own column aligned by time
    pivoted_df = df.pivot(index="time", columns="parameter_name", values="value")

    # 3. Plot key flight parameters using matplotlib (4 subplots for ALT, CAS, HDG, VS)
    print("\nGenerating flight telemetry plots...")
    fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(12, 12), sharex=True)

    # Plot Altitude (ALT)
    if "ALT" in pivoted_df.columns:
        axes[0].plot(
            pivoted_df.index,
            pivoted_df["ALT"],
            color="tab:blue",
            label="Altitude (ALT)",
        )
        axes[0].set_ylabel("Altitude")
        axes[0].grid(True, linestyle="--", alpha=0.7)
        axes[0].legend(loc="upper left")

    # Plot Airspeed (CAS)
    if "CAS" in pivoted_df.columns:
        axes[1].plot(
            pivoted_df.index,
            pivoted_df["CAS"],
            color="tab:orange",
            label="Airspeed (CAS)",
        )
        axes[1].set_ylabel("Airspeed")
        axes[1].grid(True, linestyle="--", alpha=0.7)
        axes[1].legend(loc="upper left")

    # Plot Heading (HDG)
    if "HDG" in pivoted_df.columns:
        axes[2].plot(
            pivoted_df.index,
            pivoted_df["HDG"],
            color="tab:green",
            label="Heading (HDG)",
        )
        axes[2].set_ylabel("Heading")
        axes[2].grid(True, linestyle="--", alpha=0.7)
        axes[2].legend(loc="upper left")

    # Plot Vertical Speed (VS)
    if "VS" in pivoted_df.columns:
        axes[3].plot(
            pivoted_df.index, pivoted_df["VS"], color="tab:red", label="Vert Speed (VS)"
        )
        axes[3].set_ylabel("Vert Speed")
        axes[3].legend(loc="upper left")

    axes[3].set_xlabel("Time (seconds)")
    axes[3].grid(True, linestyle="--", alpha=0.7)

    plt.suptitle("Flight Telemetry Analysis (Multi-Parameter)", fontsize=16)
    plt.tight_layout()

    # Save the generated plot to the output folder
    output_plot = parquet_path.parent / f"{parquet_path.stem}_plot.png"
    plt.savefig(output_plot, dpi=300)
    print(f"Telemetry plot saved successfully to: {output_plot}")


if __name__ == "__main__":
    sample_parquet = Path("output/decoded_flight.parquet")
    analyze_flight_data(sample_parquet)
