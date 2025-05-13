import os
import pandas as pd
import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "unanswered_log.csv")
LOG_FILE = os.path.abspath(LOG_FILE)

def log_unanswered(question, error = None):
    log_entry =  {
        "Timestamp": datetime.datetime.now().isoformat(),
        "Question": question,
        "Error": error if error else ""
    }

    # If file exists and is non-empty, read and append
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        df = pd.read_csv(LOG_FILE)
        df = pd.concat([df, pd.DataFrame([log_entry])], ignore_index=True)

    else:
        # Create a new DataFrame
        df = pd.DataFrame([log_entry])

    df.to_csv(LOG_FILE, index=False)
