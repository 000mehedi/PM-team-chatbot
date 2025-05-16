import openai

def generate_session_title(messages, openai_api_key):
    openai.api_key = openai_api_key

    transcript = ""
    for m in messages:
        role = m["role"].capitalize()
        transcript += f"{role}: {m['content']}\n"

    prompt = (
        "You are an assistant that summarizes chat conversations. "
        "Given the following conversation between a user and assistant, provide a concise session title (3 to 5 words) that best describes the main topic.\n\n"
        f"Conversation:\n{transcript}\nTitle:"
    )

    response = openai.Completion.create(
        engine="gpt-4o-mini",  # or your preferred model
        prompt=prompt,
        max_tokens=10,
        temperature=0.5,
        n=1,
        stop=["\n"]
    )
    title = response.choices[0].text.strip()
    return title
