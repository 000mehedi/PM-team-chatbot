import os
import pandas as pd
import datetime

LOG_FILE = "unanswered_log.csv"

def log_unanswered(question):
    log_entry = {
        "Timestamp": datetime.datetime.now().isoformat(),
        "Question": question
    }

    # If file exists and is non-empty, read and append
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        df = pd.read_csv(LOG_FILE)
        df = df.append(log_entry, ignore_index=True)
    else:
        # Create a new DataFrame
        df = pd.DataFrame([log_entry])

    df.to_csv(LOG_FILE, index=False)
