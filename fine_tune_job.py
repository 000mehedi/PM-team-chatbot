import os
import sys
import json
import openai
import logging

logging.basicConfig(filename="fine_tune_job.log", level=logging.INFO)

sys.path.append(os.path.join(os.path.dirname(__file__), "backend", "utils"))
from db import get_fine_tune_training_data

# 1. Get cleaned training data
pairs = get_fine_tune_training_data()
if not pairs:
    logging.info("No training data found.")
    exit(0)

# 2. Save as JSONL
jsonl_path = "fine_tune_data.jsonl"
with open(jsonl_path, "w", encoding="utf-8") as f:
    for pair in pairs:
        f.write(json.dumps(pair) + "\n")

# 3. Fine-tune with OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
upload = openai.File.create(
    file=open(jsonl_path, "rb"),
    purpose='fine-tune'
)
logging.info(f"Uploaded file ID: {upload.id}")

job = openai.FineTuningJob.create(
    training_file=upload.id,
    model="gpt-3.5-turbo"
)
logging.info(f"Started fine-tuning job: {job.id}")