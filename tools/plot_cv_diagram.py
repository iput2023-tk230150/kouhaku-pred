"""
時系列交差検証の図を作成するスクリプト
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# 設定
years = list(range(2016, 2025))  # 2016-2024
folds = [
    {"train": [2016, 2017, 2018, 2019], "test": 2020},
    {"train": [2016, 2017, 2018, 2019, 2020], "test": 2021},
    {"train": [2017, 2018, 2019, 2020, 2021], "test": 2022},
    {"train": [2018, 2019, 2020, 2021, 2022], "test": 2023},
    {"train": [2019, 2020, 2021, 2022, 2023], "test": 2024},
]

# 図の作成
fig, ax = plt.subplots(figsize=(12, 6))

# 色の設定
train_color = "#4CAF50"  # 緑
test_color = "#F44336"  # 赤
unused_color = "#E0E0E0"  # グレー

cell_height = 0.6
cell_width = 0.9

for fold_idx, fold in enumerate(folds):
    y = len(folds) - fold_idx - 1  # 上から描画

    for year_idx, year in enumerate(years):
        x = year_idx

        if year in fold["train"]:
            color = train_color
            label = "Train"
        elif year == fold["test"]:
            color = test_color
            label = "Test"
        else:
            color = unused_color
            label = ""

        # セルを描画
        rect = mpatches.FancyBboxPatch(
            (x - cell_width / 2, y - cell_height / 2),
            cell_width,
            cell_height,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            facecolor=color,
            edgecolor="white",
            linewidth=2,
        )
        ax.add_patch(rect)

# 軸の設定
ax.set_xlim(-0.7, len(years) - 0.3)
ax.set_ylim(-0.7, len(folds) - 0.3)

# X軸（年）
ax.set_xticks(range(len(years)))
ax.set_xticklabels(years, fontsize=12, fontweight="bold")
ax.set_xlabel("Year", fontsize=14, fontweight="bold")

# Y軸（Fold）
ax.set_yticks(range(len(folds)))
ax.set_yticklabels(
    [f"Fold {i + 1}" for i in range(len(folds) - 1, -1, -1)], fontsize=12
)
ax.set_ylabel("Cross-Validation Fold", fontsize=14, fontweight="bold")

# 凡例
train_patch = mpatches.Patch(color=train_color, label="Training Data (5 years)")
test_patch = mpatches.Patch(color=test_color, label="Test Data (1 year)")
unused_patch = mpatches.Patch(color=unused_color, label="Not Used")
ax.legend(
    handles=[train_patch, test_patch, unused_patch],
    loc="upper right",
    fontsize=11,
    framealpha=0.9,
)

# タイトル
ax.set_title(
    "Time Series Cross-Validation Strategy\n(Rolling Window: 5 Years Training → 1 Year Prediction)",
    fontsize=14,
    fontweight="bold",
    pad=15,
)

# グリッドを非表示
ax.set_aspect("equal")
ax.axis("off")

# X軸ラベルだけ表示
for i, year in enumerate(years):
    ax.text(i, -1.0, str(year), ha="center", va="top", fontsize=11, fontweight="bold")

# Y軸ラベル
for i in range(len(folds)):
    ax.text(
        -1.0, len(folds) - i - 1, f"Fold {i + 1}", ha="right", va="center", fontsize=11
    )

plt.tight_layout()

# 保存
output_path = "/home/omrise/2_aia/kouhaku-pred/data/analysis/cv_diagram.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"保存: {output_path}")

plt.show()
