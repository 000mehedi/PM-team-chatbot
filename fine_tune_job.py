import os
import sys
import json
import openai
import logging

logging.basicConfig(filename="fine_tune_job.log", level=logging.INFO)

sys.path.append(os.path.join(os.path.dirname(__file__), "backend", "utils"))
from db import get_fine_tune_training_data

pairs = get_fine_tune_training_data()
if not pairs:
    logging.info("No training data found.")
    exit(0)

jsonl_path = "fine_tune_data.jsonl"
with open(jsonl_path, "w", encoding="utf-8") as f:
    for pair in pairs:
        f.write(json.dumps(pair) + "\n")

openai.api_key = os.getenv("OPENAI_API_KEY")

# New API for file upload
with open(jsonl_path, "rb") as file_obj:
    file_response = openai.files.create(
        file=file_obj,
        purpose="fine-tune"
    )
file_id = file_response.id
logging.info(f"Uploaded file ID: {file_id}")

# New API for fine-tuning job
job = openai.fine_tuning.jobs.create(
    training_file=file_id,
    model="gpt-3.5-turbo"
)
logging.info(f"Started fine-tuning job: {job.id}")