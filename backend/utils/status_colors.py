def get_status_color(status):
    status_colors = {
        "closed": "#4CAF50",
        "work complete": "#4CAF50",
        "waiting on invoice": "#8BC34A",
        "assigned": "#2196F3",
        "open": "#03A9F4",
        "pm follow-up": "#FF9800",
        "cancelled": "#9E9E9E",
        "no resources": "#673AB7",
        "waiting for po": "#FFC107",
        "waiting for parts": "#FFC107",
        "suppress": "#9C27B0",
        "due today": "#FF9800",
        "past_due": "#F44336",
        "due_today": "#FF9800",
        "upcoming": "#2196F3"
    }
    if status:
        status_lower = status.lower()
        if status_lower in status_colors:
            return status_colors[status_lower]
    return "#01070C"