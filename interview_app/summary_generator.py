import json
from openai import OpenAI

def summarize_interview(questions, resume_text: str, introduction: str, OPENAI_API_KEY: str):
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = "Generate a summary of the following interview:\n\n"
    for q in questions:
        prompt += f"Topic: {q.get('topic')}\nQuestion: {q.get('question')}\nIdeal Answer: {q.get('answer')}\nCandidate Answer: {q.get('candi_answer')}\nScore: {q.get('score')}\n\n"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an interview evaluator. Follow strict JSON output."},
            {"role": "user", "content": prompt}
        ]
    )
    res = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(res)
