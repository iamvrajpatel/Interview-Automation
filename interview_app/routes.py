import os
import uuid
import json
import cv2
import numpy as np
import base64
from datetime import timedelta
from flask import render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename

from interview_app import app
from interview_app.utils import boards, grades, countries, parse_file, allowed_file, generate_hashed_id
from interview_app.demo_questions import demo_question_gpt
from interview_app.question_generator import generate_first_question, generate_next_question, categorize_answer
from interview_app.jd_parser import extract_key_points, get_subject_syllabus, interview_related_topics
from interview_app.summary_generator import summarize_interview

# Initialize other models and variables
from faster_whisper import WhisperModel
from keras_facenet import FaceNet
from mtcnn import MTCNN
from scipy.spatial.distance import euclidean

# Initialize Whisper model for transcription
model = WhisperModel("small", device="cpu", compute_type="int8")
embedder = FaceNet()
detector = MTCNN()

ALLOWED_TEXT_EXTENSIONS = {'txt', 'doc', 'docx', 'pdf'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a'}
ALLOWED_VIDEO_EXTENSIONS = {'avi', 'mp4', 'mov', 'mkv'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Use directories created in __init__.py via app config or global
BASE_DIR = os.getcwd()
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
INTERVIEW_RESULTS_DIR = os.path.join(BASE_DIR, "interview_results")
CHUNKS_DIR = os.path.join(BASE_DIR, "video_chunks")
FINAL_VIDEO_DIR = os.path.join(BASE_DIR, "videos")

# ...existing route definitions with adjustments...
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    # ...existing code...
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            session_id = generate_hashed_id()
            session['session_id'] = session_id
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOADS_DIR, filename)
            file.save(filepath)
            session['reference_img'] = filepath
            return redirect(url_for('verify', session_id=session_id))
    return render_template('upload.html')

@app.route('/verify/session_id=<session_id>')
def verify(session_id):
    if 'reference_img' not in session:
        return redirect(url_for('upload_file'))
    return render_template('verify.html', session_id=session_id)

@app.route('/api/check_face', methods=['POST'])
def check_face():
    # ...existing face-check code; unchanged except for path variables...
    if 'reference_img' not in session:
        return jsonify({'error': 'No reference image'}), 400
    
    reference_path = session['reference_img']
    reference_img = cv2.imread(reference_path)
    ref_rgb = cv2.cvtColor(reference_img, cv2.COLOR_BGR2RGB)

    ref_faces = detector.detect_faces(ref_rgb)
    if not ref_faces:
        return jsonify({'error': 'No face detected in the reference image'}), 400
    
    x, y, w, h = ref_faces[0]['box']
    ref_face = ref_rgb[y:y+h, x:x+w]
    ref_embedding = embedder.embeddings([ref_face])[0]

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    nparr = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = detector.detect_faces(rgb_frame)
    if not faces:
        return jsonify({'error': 'No face detected in the uploaded image'}), 400
    
    x, y, w, h = faces[0]['box']
    face_crop = rgb_frame[y:y+h, x:x+w]
    face_embedding = embedder.embeddings([face_crop])[0]
    distance = euclidean(ref_embedding, face_embedding)
    threshold = 0.2
    match = (1 - distance) > threshold

    return jsonify({
        'match': match,
        'confidence': 1 - distance
    })


@app.route('/success_redirect', methods=['GET'])
def success_redirect():
    return redirect(url_for('success', session_id=session['session_id']))

@app.route('/success/session_id=<session_id>')
def success(session_id):
    return render_template('success.html', session_id=session_id)

@app.route('/lets_begin', methods=["GET"])
def interview_redirect():
    return redirect(url_for('interview', session_id=session['session_id']))

@app.route('/interview/session_id=<session_id>')
def interview(session_id):
    return render_template( 
        "interview_main.html",  # Updated to use the standard filename
        boards=boards,
        grades=grades,
        countries=countries,
        session_id=session_id
    )

@app.route('/submit_form', methods=["POST"])
def submit_form():
    if request.method == "POST":
        # Handle board, grade, and subject selections
        selected_board = request.form.get("board_name")
        selected_grade = request.form.get("grade")
        selected_subject = request.form.get("subject_name")
        selected_country = request.form.get("country_name")
        
        # Handle file uploads
        job_description = None
        resume_file = None

        errors = []

        # Job Description File
        if 'job_description' in request.files:
            file = request.files['job_description']
            if file and allowed_file(file.filename, ALLOWED_TEXT_EXTENSIONS):
                filename = secure_filename(file.filename)
                job_desc_filename = f"{session['session_id']}_job_description_{filename}"
                filepath = os.path.join(UPLOADS_DIR, job_desc_filename)
                file.save(filepath)
                job_description = parse_file(filepath)
                session['job_description'] = job_description
                session['session_id'] = session['session_id']
            else:
                errors.append("Invalid Job Description file format. Please upload a valid .txt, .doc, .docx, or .pdf file.")

        # Resume File
        if 'resume' in request.files:
            file = request.files['resume']
            if file and allowed_file(file.filename, ALLOWED_TEXT_EXTENSIONS):
                filename = secure_filename(file.filename)
                resume_filename = f"{session.get('session_id', 'unknown')}_resume_{filename}"
                filepath = os.path.join(UPLOADS_DIR, resume_filename)
                file.save(filepath)
                resume_file = parse_file(filepath)
                session['candidate_resume'] = resume_file
            else:
                errors.append("Invalid Resume file format. Please upload a valid .txt, .doc, .docx, or .pdf file.")

        # Save selections in session
        session['selected_subject'] = selected_subject
        session['selected_grade'] = selected_grade
        session['selected_board'] = selected_board
        session['selected_country'] = selected_country

        if not selected_board or not selected_grade or not selected_subject:
            errors.append("Please select a board, grade, and subject.")

        if errors:
            return jsonify({"success": False, "errors": errors}), 400

        return jsonify({
            "success": True,
            "session_id": session['session_id']
            }), 200


@app.route('/start_interview', methods=['GET'])
def start_interview():
    # Initialize interview session variables
    session['questions'] = []
    session['curr_topic_index'] = 0

    # Extract session data
    job_description = session.get('job_description', '')
    selected_subject = session.get('selected_subject', '')
    selected_grade = session.get('selected_grade', '')
    selected_board = session.get('selected_board', '')
    candidate_resume = session.get('candidate_resume', '')
    session_id = session.get('session_id', '')
    selected_country = session.get('selected_country', '')

    if not all([job_description, selected_subject, selected_grade, selected_board, candidate_resume]):
        return jsonify({"error": "Missing required session data."}), 400

    # Extract key points from job description
    extracted_job_description = extract_key_points(job_description, OPENAI_API_KEY)
    session['extracted_job_description'] = extracted_job_description

    # Get subject syllabus
    subject_syllabus = get_subject_syllabus(
        extracted_job_description=extracted_job_description,
        selected_country=selected_country,
        selected_subject=selected_subject,
        selected_grade=selected_grade,
        selected_board=selected_board,
        API_KEY_OPEN_AI=OPENAI_API_KEY
    )
    session['subject_syllabus'] = subject_syllabus

    # Determine interview-related topics
    interview_topics = interview_related_topics(
        extracted_job_description=extracted_job_description,
        subject_syllabus=subject_syllabus,
        selected_grade=selected_grade,
        selected_board=selected_board,
        API_KEY_OPEN_AI=OPENAI_API_KEY
    )
    session['interview_topics_list'] = interview_topics

    # Generate demo questions
    demo_questions = demo_question_gpt(
        selected_subject=selected_subject,
        selected_grade=selected_grade,
        selected_board=selected_board,
        syllabus=subject_syllabus,
        extracted_jd=extracted_job_description,
        API_KEY_OPEN_AI=OPENAI_API_KEY
    )
    session['demo_questions'] = demo_questions['choices'][0]['message']['content']

    # Store interview topics and their limits
    session['interview_topics'] = list(session['interview_topics_list'].keys())
    session['interview_topics_limits'] = list(session['interview_topics_list'].values())

    # ---- Add Introductory Question ----
    introductory_question = """Let's start with you introducing yourself and sharing a bit about your background and teaching experience."""
    session['questions'].append({
        "topic": "Introduction",
        "question": introductory_question,
        "answer": "",
        "candi_answer": "",
        "category": "",
        "score": "",
    })
    # ---- End Introductory Question ----

    session['interview_started'] = True
    session['interview_finished'] = False

    # Save initial questions to JSON
    save_questions_to_json()
    

    return jsonify({
        "question": session["questions"][-1]
    }), 200

# Endpoint to upload each video chunk.
@app.route('/upload_video_chunk', methods=['POST'])
def upload_video_chunk():
    # Check if the POST request has the file part
    if 'video_chunk' not in request.files:
        return jsonify({'error': 'No video_chunk part in the request'}), 400

    file = request.files['video_chunk']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Optionally retrieve the chunk number to use in naming.
    chunk_number = request.form.get("chunk_number", "0")
    # Sanitize the chunk number (use secure_filename to avoid unwanted characters)
    safe_chunk_number = secure_filename(chunk_number)
    # Use a filename pattern – for example: chunk_1.webm, chunk_2.webm, etc.
    filename = f"chunk_{safe_chunk_number}.mp4"
    save_path = os.path.join(CHUNKS_DIR, filename)

    try:
        with open(save_path, "wb") as f:
            f.write(file.read())
        app.logger.info(f"Saved video chunk {filename}")
        return jsonify({'success': True, 'message': f"Chunk {safe_chunk_number} saved."})
    except Exception as e:
        app.logger.error(f"Error saving video chunk: {e}")
        return jsonify({'error': 'Failed to save chunk'}), 500
    

# Endpoint to signal the end of video upload and combine the chunks.
@app.route('/finish_video_upload', methods=['POST'])
def finish_video_upload():
    try:
        # Get a list of all chunk files
        files = os.listdir(CHUNKS_DIR)
        if not files:
            return jsonify({'error': 'No video chunks found'}), 400

        # Filter for files that match our naming pattern (chunk_*.webm)
        chunk_files = [f for f in files if f.startswith('chunk_') and f.endswith('.mp4')]
        
        # Sort the chunks in order by their number.
        # This assumes filenames are of the form "chunk_{number}.webm"
        def get_chunk_number(filename):
            try:
                base = filename.replace('chunk_', '').replace('.mp4', '')
                return int(base)
            except ValueError:
                return 0

        chunk_files.sort(key=get_chunk_number)
        app.logger.info(f"Combining chunks: {chunk_files}")

        # Name for the final video file
        final_filename = f"{session.get('session_id', 'candidate')}_rec.mp4"
        final_filepath = os.path.join(FINAL_VIDEO_DIR, final_filename)

        # Combine the chunks into the final video file
        with open(final_filepath, 'wb') as outfile:
            for chunk in chunk_files:
                chunk_path = os.path.join(CHUNKS_DIR, chunk)
                with open(chunk_path, 'rb') as infile:
                    outfile.write(infile.read())

        app.logger.info(f"Final video saved as {final_filepath}")

        # Optionally, remove the temporary chunk files after combining.
        for chunk in chunk_files:
            chunk_path = os.path.join(CHUNKS_DIR, chunk)
            os.remove(chunk_path)

        return jsonify({'success': True, 'message': 'Final video created successfully.'})
    except Exception as e:
        app.logger.error(f"Error finishing video upload: {e}")
        return jsonify({'error': 'Failed to create final video'}), 500
 

@app.route('/next_question', methods=["POST"])
def next_question():
    print("Processing next question")
    if not session.get('interview_started', False):
        return jsonify({"error": "Interview has not been started."}), 400

    data = request.json
    candidate_answer = data.get('candidate_answer', '')

    if not candidate_answer:
        return jsonify({"error": "No candidate answer provided."}), 400

    # Get the last question object
    last_question_object = session['questions'][-1]

    prev_question = last_question_object.get('question', '')
    prev_answer = last_question_object.get('answer', '')

    # Categorize the candidate's answer
    category, score, connecting_sentence = categorize_answer(
        question=prev_question,
        answer=prev_answer,
        candi_answer=candidate_answer,
        API_KEY_OPEN_AI=OPENAI_API_KEY
    )

    # Update the last question with the candidate's answer and evaluation
    
    if last_question_object['topic'] == "Introduction":
        last_question_object['answer'] = candidate_answer
    
    last_question_object['candi_answer'] = candidate_answer
    last_question_object['category'] = category
    last_question_object['score'] = 0.1 if score==0.0 else score

    # Check if the last question was the introductory question
    if last_question_object['topic'] == "Introduction":
        # Proceed to generate the first regular question based on resume and job description
        current_topic = session.get('interview_topics', [])[session.get('curr_topic_index', 0)]
        current_topic_limit = session.get('interview_topics_limits', [])[session.get('curr_topic_index', 0)]

        session['current_topic'] = current_topic
        session['current_topic_limit'] = current_topic_limit

        # Generate the first question for the current topic
        first_question, first_answer = generate_first_question(
            selected_subject=session['selected_subject'],
            selected_grade=session['selected_grade'],
            selected_board=session['selected_board'],
            subject_syllabus=session['subject_syllabus'],
            job_description=session['extracted_job_description'],
            demo_question_list=session.get('demo_questions', ''),
            curr_topic=current_topic,
            API_KEY_OPEN_AI=OPENAI_API_KEY,
            langchain_id=session['session_id'],
            introduction_of_person=session.get('introduction', '')
        )

        # Append the first question to the session
        session['questions'].append({
            "topic": current_topic,
            "question": first_question,
            "answer": first_answer,
            "candi_answer": "",
            "category": "",
            "score": "",
        })

        # Save the new question to JSON
        save_questions_to_json()

        return jsonify({
            "question": session['questions'][-1],
            "interview_finished": False,
            "connecting_sentence": connecting_sentence
        }), 200

    # Proceed with the existing flow for regular questions
    # Check if we need to move to the next topic
    current_topic = session.get('current_topic', 'general')
    current_topic_limit = session.get('current_topic_limit')
    questions_count = sum(1 for q in session['questions'] if q['topic'] == current_topic)

    if questions_count >= current_topic_limit:
        # Save current topic's questions to JSON
        save_questions_to_json()

        # Check if there are more topics
        if session['curr_topic_index'] + 1 < len(session['interview_topics']):
            # Move to next topic
            session['curr_topic_index'] += 1
            next_topic = session['interview_topics'][session['curr_topic_index']]
            next_topic_limit = session['interview_topics_limits'][session['curr_topic_index']]

            session['current_topic'] = next_topic
            session['current_topic_limit'] = next_topic_limit

            # Generate the first question for the new topic
            next_question, next_answer = generate_first_question(
                selected_subject=session['selected_subject'],
                selected_grade=session['selected_grade'],
                selected_board=session['selected_board'],
                subject_syllabus=session['subject_syllabus'],
                job_description=session['extracted_job_description'],
                demo_question_list=session['demo_questions'],
                curr_topic=next_topic,
                API_KEY_OPEN_AI=OPENAI_API_KEY,
                langchain_id=session['session_id'],
                introduction_of_person=session.get('introduction', '')
            )

            # Append the first question to the session
            session['questions'].append({
                "topic": next_topic,
                "question": next_question,
                "answer": next_answer,
                "candi_answer": "",
                "category": "",
                "score": "",
            })

            # Save the new topic's questions to JSON
            save_questions_to_json()

            return jsonify({
                "question": session['questions'][-1],
                "interview_finished": False,
                "connecting_sentence": connecting_sentence
            }), 200

        else:
            # No more topics, interview is finished
            # Save final questions to JSON
            save_questions_to_json()

            session['interview_finished'] = True

            # Save the video file path
            session['video_filename'] = f"{session.get('session_id', 'unknown')}_interview_video.avi"
            
            return jsonify({
                "interview_finished": True
            }), 200

    else:
        # Generate the next question within the current topic
        next_question, next_answer = generate_next_question(
            subject_syllabus=session['subject_syllabus'],
            selected_grade=session['selected_grade'],
            selected_board=session['selected_board'],
            selected_subject=session['selected_subject'],
            curr_topic=session['current_topic'],
            resume_of_person=session['candidate_resume'],
            introduction_of_person=session.get('introduction', ''),
            langchain_id=session['session_id'],
            API_KEY_OPEN_AI=OPENAI_API_KEY
        )

        session['questions'].append({
            "topic": session['current_topic'],
            "question": next_question,
            "answer": next_answer,
            "candi_answer": "",
            "category": "",
            "score": "",
        })

        # Save the new question to JSON
        save_questions_to_json()

        return jsonify({
            "question": session['questions'][-1],
            "interview_finished": False,
            "connecting_sentence": connecting_sentence
        }), 200

@app.route("/get_questions", methods=["GET"])
def get_questions():
    if not session.get('interview_started', False):
        return jsonify({"error": "Interview has not been started."}), 400

    ret_json = {
        "questions": session["questions"]
    }

    return ret_json

# Function to save questions to a JSON file
def save_questions_to_json():
    if 'session_id' not in session:
        print("No session_id found. Cannot save questions.")
        return

    session_id = session['session_id']
    current_topic = session.get('current_topic', 'general')
    filename = f"{session_id}_all_questions.json"
    file_path = os.path.join(INTERVIEW_RESULTS_DIR, filename)

    # Extract questions related to the current topic
    topic_questions = [q for q in session['questions']]

    # Save the topic's questions
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(topic_questions, f, ensure_ascii=False, indent=4)

    print(f"Saved interview questions to {file_path}")


# Route to handle audio upload and transcription
@app.route("/upload_audio_chunk", methods=["POST"])
def upload_audio_chunk():
    file_id = request.form.get("file_id")
    try:
        chunk_number = int(request.form.get("chunk_number", 0))
    except ValueError:
        return jsonify({"error": "Invalid chunk number"}), 400

    if not file_id:
        return jsonify({"error": "Missing file_id"}), 400

    if "audio_chunk" not in request.files:
        return jsonify({"error": "No audio chunk provided"}), 400

    audio_chunk = request.files["audio_chunk"]

    # Use a safe filename based on file_id.
    filename = secure_filename(file_id) + ".wav"
    file_path = os.path.join(UPLOADS_DIR, filename)

    # For the first chunk, write a new file; for subsequent chunks, append.
    mode = "wb" if chunk_number == 1 else "ab"
    try:
        with open(file_path, mode) as f:
            f.write(audio_chunk.read())
    except Exception as e:
        return jsonify({"error": f"Error writing chunk: {str(e)}"}), 500

    return jsonify({"success": True, "chunk_number": chunk_number})

@app.route("/finish_audio_upload", methods=["POST"])
def finish_audio_upload():
    data = request.get_json()
    file_id = data.get("file_id")
    if not file_id:
        return jsonify({"error": "Missing file_id"}), 400

    filename = secure_filename(file_id) + ".wav"
    file_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # Transcribe the complete audio file.
    try:
        transcription = transcribe_audio(file_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Optionally, remove the temporary file after processing.
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify({"transcription": transcription})

def transcribe_audio(file_path):
    """
    Transcribe the audio file using faster-whisper.
    Returns a string containing the transcription.
    """
    segments, info = model.transcribe(file_path)
    transcription = " ".join([segment.text for segment in segments])
    return transcription


@app.route('/end_interview', methods=['POST'])
def end_interview():
    save_questions_to_json()
    try:
        data = request.get_json()
        session_id = session['session_id']
        
        filename = os.path.join(INTERVIEW_RESULTS_DIR, f"{session_id}_all_questions.json")
        
        # Read the JSON file
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                questions = json.load(file)
        except FileNotFoundError:
            return jsonify({"error": f"File '{filename}' not found."}), 404
        except json.JSONDecodeError:
            return jsonify({"error": f"File '{filename}' is not a valid JSON file."}), 400
            
        # Prepare the prompt for GPT
        summary = summarize_interview(questions=questions, 
                                            resume_text=session.get('candidate_resume', ''), 
                                            introduction=session.get('introduction', ''), 
                                            OPENAI_API_KEY=OPENAI_API_KEY)
        
        return {'summary' : summary}

    except Exception as e:
        return jsonify({'error': str(e)}), 500
