from pathlib import Path
import matplotlib.pyplot as plt

attempts = [0, 1, 2]
compilation_success = [37.65, 46.30, 53.62]
runtime_success = [66.67, 76.24, 78.39]

output_dir = Path("results/validity_repair")
output_dir.mkdir(exist_ok=True)

plt.figure(figsize=(6, 4))
plt.plot(attempts, compilation_success, marker="o", label="Compilation success")
plt.plot(attempts, runtime_success, marker="s", label="Runtime success")

plt.xlabel("Maximum repair attempts")
plt.ylabel("Success percentage (%)")
plt.title("Test Validity Across Different Numbers of Repair Attempts")
plt.xticks(attempts)
plt.ylim(0, 100)
plt.grid(True, axis="y", linestyle="--", alpha=0.5)
plt.legend()
plt.tight_layout()

plt.savefig(output_dir / "test_validity_repair_attempts.pdf")
plt.savefig(output_dir / "test_validity_repair_attempts.png", dpi=300)
plt.close()