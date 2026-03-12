"""Shared Plotly color palette and chart helpers."""

# 12-color palette -- distinct, accessible, works on dark backgrounds
CATEGORY_COLORS = {
    "Housing": "#4C78A8",
    "Taxes & Fees": "#F58518",
    "Insurance": "#E45756",
    "Student Loan": "#72B7B2",
    "Debt Payment": "#54A24B",
    "Food & Drink": "#EECA3B",
    "Groceries": "#B279A2",
    "Shopping": "#FF9DA6",
    "Bills & Utilities": "#9D755D",
    "Health & Wellness": "#BAB0AC",
    "Personal": "#D67195",
    "Automotive": "#2196F3",
    "Travel": "#7B66D2",
    "Entertainment": "#A0CBE8",
    "Gas": "#8CD17D",
    "Home": "#B6992D",
    "Professional Services": "#499894",
    "Uncategorized": "#79706E",
}

DEFAULT_COLOR = "#79706E"


def get_color_sequence(categories: list[str]) -> list[str]:
    """Return a list of colors matching the given category order."""
    return [CATEGORY_COLORS.get(cat, DEFAULT_COLOR) for cat in categories]


PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
    margin=dict(l=40, r=20, t=40, b=40),
)
