import os
from openai import OpenAI

def demo_question_gpt(selected_board: str, selected_subject: str, extracted_jd: str, selected_grade: str, syllabus: str, API_KEY_OPEN_AI: str):
    prompt = [{
        "role": "system",
        "content": f"""
            Generate 10 creative interview questions for a teacher where the subject is {selected_subject}.
            The questions should be brief, thought-provoking and based on the syllabus:
            {syllabus}
            ***RETURN QUESTIONS WITHOUT NUMBERING***
        """
    }, {
        "role": "user",
        "content": f"Generate 10 questions for a teacher interview based on: {extracted_jd}"
    }]
    openai_client = OpenAI(api_key=API_KEY_OPEN_AI)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=prompt,
        temperature=0.7
    )
    return response.to_dict()
