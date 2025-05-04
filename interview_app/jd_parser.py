import json
from openai import OpenAI

def extract_key_points(job_description: str, API_KEY_OPEN_AI: str):
    client = OpenAI(api_key=API_KEY_OPEN_AI)
    prompty = f"""
        Extract the most relevant keywords from the following job description:
        {job_description}
        ***RETURN ONLY JSON IN THE GIVEN FORMAT***
        {{
            "Job Title": STRING,
            "Skills": ["Skill 1", "Skill 2"],
            "Qualifications": ["Qualification 1"],
            "Responsibilities": ["Responsibility 1"],
            "Experience": {{
                "Experience Level": "Level",
                "Experience Relevance": ["Field 1"]
            }},
            "Industry": "Industry",
            "Tools/Technologies": ["Tool 1"],
            "Other Requirements": ["Requirement 1"]
        }}
        """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract key points from JD."},
            {"role": "user", "content": prompty}
        ]
    )
    res = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(res)

def interview_related_topics(extracted_job_description: str, selected_board: str, selected_grade: str, 
                             subject_syllabus: str, API_KEY_OPEN_AI: str):
    client = OpenAI(api_key=API_KEY_OPEN_AI)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Extract interview topics from: {extracted_job_description}"},
            {"role": "system", "content": f"Return topics (max 3) with allocated minutes summing 4 based on syllabus: ```{subject_syllabus}```"}
        ]
    )
    res = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(res)

def get_subject_syllabus(extracted_job_description: str, selected_country: str, selected_board: str, 
                         selected_subject: str, selected_grade: str, API_KEY_OPEN_AI: str):
    client = OpenAI(api_key=API_KEY_OPEN_AI)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Syllabus for {selected_subject} for country {selected_country}, board {selected_board}, grade {selected_grade}:"},
            {"role": "system", "content": f"Use the extracted JD: {extracted_job_description}. Return syllabus only."}
        ]
    )
    return response.choices[0].message.content
