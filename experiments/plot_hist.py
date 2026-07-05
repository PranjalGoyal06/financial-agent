import json
import pandas as pd
import matplotlib.pyplot as plt

with open("sample_imports/history.json") as f:
    data = json.load(f)

df = pd.DataFrame(data["bars"])
df["date"] = pd.to_datetime(df["date"])

fig, (ax1, ax2) = plt.subplots(
    2, 1,
    figsize=(14, 8),
    sharex=True,
    gridspec_kw={"height_ratios": [3, 1]}
)

# Closing price
ax1.plot(df["date"], df["close"], linewidth=2)
ax1.set_title(f'{data["ticker"]} Closing Price')
ax1.set_ylabel("Price")

# Volume
ax2.bar(df["date"], df["volume"])
ax2.set_ylabel("Volume")
ax2.set_xlabel("Date")

plt.xticks(rotation=45)
plt.tight_layout()
plt.show()