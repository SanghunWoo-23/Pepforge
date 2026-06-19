
#  Peptide Design Engine - Auto Analysis Script

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
csv_path = os.path.join(OUTPUT_DIR, "results_top.csv")

if not os.path.exists(csv_path):
    raise FileNotFoundError("results_top.csv not found")

df = pd.read_csv(csv_path)

print("Loaded rows:", len(df))

# Score distribution
plt.figure()
sns.histplot(df["total_score"], bins=30)
plt.title("Score Distribution")
plt.savefig("score_distribution.png")
plt.close()

# Length distribution
plt.figure()
sns.histplot(df["length"], bins=20)
plt.title("Length Distribution")
plt.savefig("length_distribution.png")
plt.close()

# Hotspot match
def parse_hotspot_map(x):
    if pd.isna(x):
        return []
    return [i.split(":")[1] for i in str(x).split("|") if ":" in i]

all_matches = []
for m in df.get("hotspot_peptide_map", []):
    all_matches.extend(parse_hotspot_map(m))

if all_matches:
    pd.Series(all_matches).value_counts().plot(kind="bar")
    plt.title("Hotspot Match Distribution")
    plt.savefig("hotspot_match.png")
    plt.close()

# Docking readiness
if "category" in df.columns:
    df["category"].value_counts().plot(kind="bar")
    plt.title("Docking Readiness")
    plt.savefig("docking_ready.png")
    plt.close()

# Best hotspot
if "best_hotspot" in df.columns:
    df["best_hotspot"].value_counts().head(10).plot(kind="bar")
    plt.title("Top Hotspots")
    plt.savefig("top_hotspots.png")
    plt.close()

print("Analysis images saved.")
