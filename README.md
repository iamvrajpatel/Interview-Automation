# Interview Autobot (Flask)

An end-to-end AI-powered interview automation platform for recruitment, featuring face verification, document upload, dynamic question generation, audio/video recording, and automated evaluation using OpenAI.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/iamvrajpatel/Interview-Autobot-Flask.git
cd ./Interview-Autobot-Flask
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Configuration

This project uses a `.env` file to store environment variables.

1. **Create a `.env` file** in the project root.
2. **Add at least:**

```bash
OPENAI_API_KEY="your_openai_api_key_here"
```

---

## Running the Application

To start the app, run:

```bash
python main.py
```

The app will be available at `http://localhost:5000/`.

---

## Project Overview & Flow

### 1. **Face Verification**

- **Landing Page:** The user is prompted to upload a photo ID (image file).
- **Reference Image:** The uploaded image is stored and used as the reference for face verification.
- **Live Verification:** The user is redirected to a webcam page. The app captures frames and compares the live face to the reference image using FaceNet and MTCNN.
- **Access Control:** Only if the face matches, the user can proceed to the interview. Otherwise, options for retry or manual verification are provided.

### 2. **Document Upload & Interview Setup**

- **Form Inputs:** The user selects:
  - Country
  - Board (e.g., CBSE, IB)
  - Grade (Primary, Secondary, Higher Secondary)
  - Subject (populated based on grade)
- **File Uploads:** The user uploads:
  - Job Description (JD) file (`.txt`, `.doc`, `.docx`, `.pdf`)
  - Resume file (`.txt`, `.doc`, `.docx`, `.pdf`)
- **Validation:** The backend checks file types and required fields.

### 3. **Interview Initialization**

- **Key Extraction:** The backend uses OpenAI to extract key points from the JD and generate a subject syllabus.
- **Topic Allocation:** The system determines 2-3 main interview topics and allocates time for each (total 4 minutes).
- **Demo Questions:** Example questions are generated for context.
- **Session State:** All selections and extracted data are stored in the session.

### 4. **Interview Process**

- **Video Recording:** The user's webcam and microphone are activated. Video is chunked and uploaded to the server.
- **Question Flow:**
  - The interview starts with an introduction prompt.
  - For each topic, the system generates questions using OpenAI, considering the JD, syllabus, and candidate's background.
  - Each question is spoken aloud (TTS) and displayed.
  - After a countdown, the user's audio answer is recorded and uploaded in chunks.
  - The answer is transcribed using Whisper.
  - The system evaluates the answer (clarity, relevance, depth, examples) and scores it.
  - A connecting sentence is spoken, and the next question is generated.
- **Topic Progression:** After the allocated number of questions per topic, the interview moves to the next topic.
- **Completion:** After all topics/questions, the interview ends.

### 5. **Post-Interview & Evaluation**

- **Summary:** The system calculates topic-wise average scores and generates a comprehensive evaluation using OpenAI, including:
  - Key strengths and weaknesses
  - Final recommendation (Shortlisted, On Hold, Rejected)
  - Justification based on answers, resume, and introduction
- **Results Display:** The UI shows:
  - All questions and candidate answers with scores
  - Topic-wise averages
  - Evaluation summary and recommendation

---

## UI Flow (Step-by-Step)

1. **Upload Photo ID:**  
   - Go to `/` and upload your image.
2. **Face Verification:**  
   - Allow webcam access and follow on-screen instructions.
   - If verified, click "Move Forward for Interview".
3. **Interview Setup:**  
   - Fill out the form: select country, board, grade, subject.
   - Upload your JD and resume.
   - Click "Start Interview".
4. **Interview:**  
   - The system will ask questions (audio + text).
   - Listen, then answer aloud after the countdown.
   - Your answers are recorded and transcribed.
   - The process repeats for all topics/questions.
5. **Results:**  
   - After the interview, view your answers, scores, and the AI-generated summary.

---

## File Structure

- `main.py` — Entry point; bootstraps the Flask app.
- `interview_app/`
  - `__init__.py` — Initializes the Flask app and configuration.
  - `routes.py` — All route definitions.
  - `utils.py` — Utility functions (file parsing, allowed extensions, etc).
  - `question_generator.py` — OpenAI-powered question and evaluation logic.
  - `jd_parser.py` — Job description parsing and topic extraction.
  - `summary_generator.py` — Final interview summary and recommendation logic.
  - `demo_questions.py` — Generation of demo interview questions.
- `templates/` — HTML templates.
- `static/` — CSS and JavaScript files.

---

## Notes

- **OpenAI API usage:** Ensure your API key has sufficient quota.
- **Video/Audio:** All media is processed and stored server-side for evaluation.
- **Session:** Interview state is maintained via Flask session.
- **Customization:** You can extend boards, grades, or subjects in `utils.py`.

---

## Troubleshooting

- If you encounter errors with file uploads, check file types and sizes.
- For webcam/microphone issues, ensure browser permissions are granted.
- For OpenAI errors, verify your API key and quota.

---

## License

MIT License
DONe
---
