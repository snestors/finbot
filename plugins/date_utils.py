import datetime

def register():
    return {
        "tools": {
            "get_day_of_week": {
                "description": "Returns the day of the week for 'today' or 'tomorrow' in Spanish.",
                "handler": get_day_of_week,
            },
        },
        "actions": {},
    }

def get_day_of_week(params: dict) -> str:
    """Sync tool — returns the day of the week for 'today' or 'tomorrow'."""
    offset = params.get("offset", 0) # 0 for today, 1 for tomorrow
    days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    
    date_to_check = datetime.datetime.now() + datetime.timedelta(days=offset)
    day_index = date_to_check.weekday()
    return days[day_index]
