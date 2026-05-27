from pathlib import Path
import matplotlib.pyplot as plt

attempts = [0, 1, 2]
compilation_success = [38.97, 48.72, 50.77]
runtime_success = [71.26, 78.92, 79.24]

output_dir = Path("results/test_validity")
output_dir.mkdir(exist_ok=True)

plt.figure(figsize=(6, 4))
plt.plot(attempts, compilation_success, marker="o", label="Compilation success")
plt.plot(attempts, runtime_success, marker="s", label="Runtime success")

# Add value labels above each point
for x, y in zip(attempts, compilation_success):
    plt.text(x, y + 2, f"{y:.1f}%", ha="center", va="bottom", fontsize=9)

for x, y in zip(attempts, runtime_success):
    plt.text(x, y + 2, f"{y:.1f}%", ha="center", va="bottom", fontsize=9)

plt.xlabel("Maximum repair attempts")
plt.ylabel("Success percentage (%)")
plt.title("Test Validity Across Different Numbers of Repair Attempts")
plt.xticks(attempts)
plt.ylim(0, 100)
plt.grid(True, axis="y", linestyle="--", alpha=0.5)
plt.legend()
plt.tight_layout()

# plt.savefig(output_dir / "test_validity_repair_attempts.pdf")
plt.savefig(output_dir / "test_validity_repair_attempts.png", dpi=300)
plt.close()