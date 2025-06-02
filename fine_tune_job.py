import os
import sys
import json
import openai
import logging
from datetime import datetime, timedelta

logging.basicConfig(filename="fine_tune_job.log", level=logging.INFO)

sys.path.append(os.path.join(os.path.dirname(__file__), "backend", "utils"))
from db import get_prompt_completion_pairs  # We'll use a custom function for recent data

openai.api_key = os.getenv("OPENAI_API_KEY")

def is_flagged(text):
    response = openai.moderations.create(input=text)
    return response.results[0].flagged

def get_recent_prompt_completion_pairs(days=30):
    """
    Returns prompt-completion pairs from only the last `days` days.
    Assumes each pair has a 'timestamp' field (from the user message).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    pairs = []
    all_pairs = get_prompt_completion_pairs()
    for pair in all_pairs:
        timestamp = pair.get("timestamp")
        if timestamp:
            try:
                msg_dt = datetime.strptime(timestamp[:19], "%Y-%m-%d %H:%M:%S")
                if msg_dt < cutoff:
                    continue
            except Exception:
                continue
        pairs.append(pair)
    return pairs

# 1. Get only recent training data (e.g., last 30 days)
pairs = get_recent_prompt_completion_pairs(days=7)
if not pairs:
    logging.info("No training data found.")
    exit(0)

# 2. Write and moderate the training data
jsonl_path = "fine_tune_data.jsonl"
clean_jsonl_path = "clean_fine_tune_data.jsonl"
with open(jsonl_path, "w", encoding="utf-8") as f:
    for pair in pairs:
        f.write(json.dumps({
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": pair["prompt"]},
                {"role": "assistant", "content": pair["completion"]}
            ]
        }) + "\n")

with open(jsonl_path, "r", encoding="utf-8") as infile, \
     open(clean_jsonl_path, "w", encoding="utf-8") as outfile:
    for line in infile:
        data = json.loads(line)
        flagged = False
        for msg in data["messages"]:
            if is_flagged(msg["content"]):
                flagged = True
                break
        if not flagged:
            outfile.write(line)

# 3. Fine-tune with the cleaned file
with open(clean_jsonl_path, "rb") as file_obj:
    file_response = openai.files.create(
        file=file_obj,
        purpose="fine-tune"
    )
file_id = file_response.id
logging.info(f"Uploaded file ID: {file_id}")

job = openai.fine_tuning.jobs.create(
    training_file=file_id,
    model="gpt-3.5-turbo-0125"
)
logging.info(f"Started fine-tuning job: {job.id}")