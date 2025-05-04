import json
from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

def generate_first_question(selected_board: str, selected_subject: str, selected_grade: str, curr_topic: str, 
                            subject_syllabus: str, job_description: str, API_KEY_OPEN_AI: str, 
                            introduction_of_person: str, demo_question_list: str, langchain_id: str):
    job_description = job_description.replace("{", "{{").replace("}", "}}")
    json_format = """ "question": [Generated Question], "answer": [Generated Answer] """
    template = f"""
        ***YOU ARE A TEACHER INTERVIEW AUTOBOT***
        ...instructions...
        Generate the Question and Answer in the given JSON format below:
        {json_format}
        
        **RETURN JSON FORMAT ONLY**
        """
    llm = ChatOpenAI(api_key=API_KEY_OPEN_AI, model="gpt-4o-mini")
    prompt = PromptTemplate(template=template, input_variables=[])
    memory = ConversationBufferMemory(memory_key=langchain_id, return_messages=True)
    llm_chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    response = llm_chain.run({"subject_syllabus": subject_syllabus})
    res = response.replace("```json", "").replace("```", "").strip()
    data = json.loads(res)
    return data["question"], data["answer"]

def generate_next_question(selected_board: str, selected_subject: str, selected_grade: str, curr_topic: str, 
                           subject_syllabus: str, API_KEY_OPEN_AI: str, introduction_of_person: str, 
                           resume_of_person: str, langchain_id: str):
    json_format = """ "question": [Generated Question], "answer": [Generated Answer for the Generated Question] """
    template = f"""
        *** GENERATE ONLY ONE QUESTION FOR THE INTERVIEW OF A TEACHER ***
        ...instructions...
        Generate the Question and Answer in the given JSON format below:
        {json_format}
        
        **RETURN JSON FORMAT ONLY**
        """
    llm = ChatOpenAI(api_key=API_KEY_OPEN_AI, model="gpt-4o-mini")
    prompt = PromptTemplate(template=template, input_variables=["subject", "job_description", "previous_que", "previous_ans", "introduction_of_person", "demo_question_list"])
    from langchain.memory import ConversationBufferMemory
    memory = ConversationBufferMemory(memory_key=langchain_id, return_messages=True)
    llm_chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    context = {"introduction": introduction_of_person} if introduction_of_person is not None else {"introduction": resume_of_person}
    response = llm_chain.run(context)
    res = response.replace("```json", "").replace("```", "").strip()
    data = json.loads(res)
    return data["question"], data["answer"]

def categorize_answer(question: str, answer: str, candi_answer: str, API_KEY_OPEN_AI:str):
    json_format = """ "category": [Category], "score": [Score], "connecting_sentence": [Connecting Sentence] """
    template = f"""
        Inputs Provided to Prompt:
        - Question: {question}
        - Ideal Answer: {answer}
        - Candidate Answer: {candi_answer}
        ...evaluation instructions...
        Generate the response in the JSON format below:
        {json_format}
        """
    from openai import OpenAI
    client = OpenAI(api_key=API_KEY_OPEN_AI)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "You are an interview analyser."},
            {"role": "system", "content": template}
        ]
    )
    res = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    data = json.loads(res)
    return data["category"], data["score"], data["connecting_sentence"]
