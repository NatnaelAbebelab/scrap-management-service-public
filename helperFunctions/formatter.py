
def format_large_number(value):
    if value >= 1_000_000_000:  # Billion
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:  # Million
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:  # Thousand
        return f"{value / 1_000:.1f}K"
    return str(value) 