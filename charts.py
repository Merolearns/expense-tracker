"""Matplotlib charts, saved to PNG files (no GUI needed)."""
import db


def category_bar_chart(conn, month, out_path):
    """Bar chart of spending by category for a month. Returns the output path."""
    import matplotlib

    matplotlib.use("Agg")  # headless -- works fine on servers
    import matplotlib.pyplot as plt

    totals = db.category_totals(conn, month)
    if not totals:
        raise ValueError(f"nothing to chart for {month}")

    categories = [cat for cat, _ in totals]
    amounts = [total for _, total in totals]

    # horizontal bars read better when category names get long
    fig, ax = plt.subplots(figsize=(8, max(3, 0.6 * len(categories))))
    bars = ax.barh(categories, amounts, color="#4a7c59")
    ax.set_xlabel("Spent ($)")
    ax.set_title(f"Spending by category - {month}")
    ax.invert_yaxis()  # biggest spender on top
    for bar, amount in zip(bars, amounts):
        ax.text(bar.get_width() + max(amounts) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"${amount:,.2f}", va="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
