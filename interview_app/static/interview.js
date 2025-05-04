document.addEventListener("DOMContentLoaded", () => {
    // Get the video element and start the local video stream
    let localVideo = document.getElementById('localVideo');
    let videoInterval; // To store the interval ID for video frame capturing
    let localStream;

    // *** Variables for recording the local stream (video with audio) ***
    let videoMediaRecorder;
    // A counter for keeping track of chunk numbers
    let videoChunkCount = 0;

    // Function to send a video chunk (as a Blob) to the Flask server
    async function sendVideoChunk(chunkBlob, chunkNumber) {
        try {
            const formData = new FormData();
            formData.append("video_chunk", chunkBlob, `chunk_${chunkNumber}.mp4`);
            // Optionally send a chunk index so that server can track order
            formData.append("chunk_number", chunkNumber);

            // Send the chunk to your Flask endpoint (adjust the URL as needed)
            await fetch("/upload_video_chunk", {
                method: "POST",
                body: formData        
            });
        } catch (error) {
            console.error("Error sending video chunk:", error);
        }
    }

    // Function to signal the end of video upload to the server,
    // so that the server can combine and store the chunks.
    async function signalVideoUploadFinished() {
        try {
            await fetch("/finish_video_upload", {
                method: "POST"
            });
            console.log("Signaled server to finish video upload.");
        } catch (error) {
            console.error("Error finishing video upload:", error);
        }
    }

    // Function to start capturing video from the webcam
    async function startLocalStream() {
        try {
            // Access user's webcam and microphone
            localStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, frameRate: 15, bitrate: 250000 }, // Adjust resolution as needed
                audio: true
            });
            localVideo.srcObject = localStream;
            localVideo.style.display = 'block'; // Show the video element
            console.log('Local stream started');

            // Start recording the complete local stream (video + audio)
            // Using MIME type "video/webm" with VP8 and Opus codecs (may vary by browser)
            videoMediaRecorder = new MediaRecorder(localStream, {
                mimeType: 'video/webm; codecs=vp9',
            });
            videoChunkCount = 0; // Reset the counter

            // Set up the ondataavailable event to send video chunks as soon as they are available.
            videoMediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    videoChunkCount++;
                    // Instead of saving the chunk locally, send it to the server.
                    sendVideoChunk(e.data, videoChunkCount);
                }
            };

            // Start the MediaRecorder with a timeslice in milliseconds.
            // This causes ondataavailable to be called at regular intervals.
            videoMediaRecorder.start(2000); // e.g., every 2 seconds
            console.log('MediaRecorder for local stream started');

            // (Optional) If you still need to capture and send canvas frames,
            // the code below remains for other purposes—but it is not used for video storage.
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');

            videoInterval = setInterval(() => {
                if (localVideo.readyState === localVideo.HAVE_ENOUGH_DATA) {
                    canvas.width = localVideo.videoWidth;
                    canvas.height = localVideo.videoHeight;
                    ctx.drawImage(localVideo, 0, 0, canvas.width, canvas.height);
                }
            }, 1000 / 30); // 30 FPS
        } catch (error) {
            console.error('Error accessing webcam:', error);
            alert('Could not access your webcam. Please check permissions.');
        }
    }

    // Function to stop the local video stream and end the video upload on the server
    function stopLocalStream() {
        // First, stop the MediaRecorder for the local stream if it is recording
        if (videoMediaRecorder && videoMediaRecorder.state !== "inactive") {
            videoMediaRecorder.stop();
        }

        // Then, stop all media tracks in the localStream
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localVideo.srcObject = null;
            console.log('Local video stream stopped');
            localStream = null;
        }

        // Clear the video capturing interval if it was used for other purposes
        if (videoInterval) {
            clearInterval(videoInterval);
            videoInterval = null;
            console.log('Video frame capturing interval cleared');
        }
        signalVideoUploadFinished();
    }

    // ===================== Interview and Audio Recording Code =====================
    let mediaRecorder;
    let audioChunks = [];
    let stream;
    let curr_transcription = "";
    let currentQuestion = "";
    let currentTopic = "";
    let interviewFinished = false;

    // Silence Detection Variables
    let audioContext;
    let microphone;

    // Helper function to upload the audio Blob in 1 MB chunks
    async function uploadAudioBlobInChunks(blob, fileId, chunkSize = 512 * 1024) {
        const totalSize = blob.size;
        let offset = 0;
        let chunkNumber = 1;
        while (offset < totalSize) {
            const chunk = blob.slice(offset, offset + chunkSize);
            const formData = new FormData();
            formData.append("file_id", fileId);
            formData.append("chunk_number", chunkNumber);
            formData.append("audio_chunk", chunk, `chunk_${chunkNumber}.wav`);

            try {
                // const formDataBlob = new Blob([...formData]);
                // console.log(`Size of FormData (approx): ${formDataBlob.size / 1024 ** 2} MB`);

                const response = await fetch("/upload_audio_chunk", {
                    method: "POST",
                    body: formData
                });
                const result = await response.json();
                if (!result.success) {
                    throw new Error("Chunk upload failed: " + result.error);
                }
            } catch (error) {
                console.error("Error uploading chunk:", error);
                throw error;
            }
            offset += chunkSize;
            chunkNumber++;
        }
        // After all chunks have been uploaded, signal the server that the upload is complete.
        try {
            const finishResponse = await fetch("/finish_audio_upload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file_id: fileId })
            });
            const finishResult = await finishResponse.json();
            if (finishResult.error) {
                console.error("Error finishing upload:", finishResult.error);
                document.getElementById("transcription").innerText = "Error finishing upload: " + finishResult.error;
            } else if (!finishResult.transcription || finishResult.transcription.trim() === "") {
                console.warn("No transcription received");
                document.getElementById("transcription").innerText = "No transcription detected. Please try again.";
                restartRecording();
            } else {
                document.getElementById("transcription").innerText = "Transcription: " + finishResult.transcription;
                curr_transcription = finishResult.transcription;
                console.log("Transcription received:", finishResult.transcription);
                submitAnswer();
            }
        } catch (error) {
            console.error("Error finishing upload:", error);
            document.getElementById("transcription").innerText = "Error finishing upload.";
            throw error;
        }
    }

    // Handle form submission with loading spinner
    document.getElementById('interview-form').addEventListener('submit', function (event) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);

        document.getElementById('loading-spinner').style.display = 'inline-block';
        document.getElementById('start-button').disabled = true;

        fetch('/submit_form', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    alert(`Errors:\n- ${data.errors.join('\n- ')}`);
                    document.getElementById('loading-spinner').style.display = 'none';
                    document.getElementById('start-button').disabled = false;
                } else {
                    if (isCameraAccessAllowed()) {
                        initiateInterview();
                    } else {
                        console.error("Please Allow the Camera Access!!");
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while submitting the form.');
                document.getElementById('loading-spinner').style.display = 'none';
                document.getElementById('start-button').disabled = false;
            });
    });

    async function isCameraAccessAllowed() {
        try {
            // Try to access the camera
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            // If successful, release the camera and return true
            stream.getTracks().forEach(track => track.stop());
            return true;
        } catch (error) {
            return false;
        }
    }

    // Function to start the interview after form submission
    function initiateInterview() {
        startLocalStream();

        fetch('/start_interview', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(`Error: ${data.error}`);
                    document.getElementById('loading-spinner').style.display = 'none';
                    document.getElementById('start-button').disabled = false;
                    return;
                }

                // Hide the start section and show the interview questions section
                document.getElementById('start-interview-section').style.display = 'none';
                document.getElementById('interview-questions-section').style.display = 'block';
                document.getElementById('loading-spinner').style.display = 'none';

                // First, speak the introduction from Chitti.
                speakQuestion("Hello, and thank you for joining me today. My name is Chitti, and I'm part of the hiring team for this teaching position. We're excited to learn more about your expertise and teaching philosophy.", function() {
                    // After the introduction is finished, display and speak the first question.
                    displayQuestion(data.question.topic, data.question.question);
                });
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while starting the interview.');
                document.getElementById('loading-spinner').style.display = 'none';
                document.getElementById('start-button').disabled = false;
            });
    }

    // Display Question with TTS
    function displayQuestion(topic, question) {
        currentQuestion = question;
        currentTopic = topic;
        document.getElementById('topic-display').innerHTML = `<strong>Topic:</strong> ${topic}`;
        document.getElementById('question-display').innerText = `Question: ${question}`;
        document.getElementById('transcription').innerText = "";
        document.getElementById('player').src = "";

        document.getElementById("record").style.display = 'none';

        // Speak the question, and when finished, start the countdown.
        speakQuestion(question, () => {
            console.log('Question spoken:', question);
            startCountdown(4);
            console.log('Speech ended, starting countdown');
        });
    }

    // Function to perform Text-to-Speech with callback
    function speakQuestion(text, callback) {
        console.log('Speaking:', text);
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            const voices = speechSynthesis.getVoices();
            const desiredVoice = voices.find(voice => voice.name === 'Google UK English') || voices[0];
            utterance.voice = desiredVoice;
            utterance.pitch = 1;
            utterance.rate = 1;
            if (voices.length === 0) {
                speechSynthesis.onvoiceschanged = () => {
                    const updatedVoices = speechSynthesis.getVoices();
                    utterance.voice = updatedVoices.find(voice => voice.name === 'Google UK English') || updatedVoices[0];
                    utterance.onend = callback;
                    speechSynthesis.speak(utterance);
                };
            } else {
                utterance.onend = callback;
                speechSynthesis.speak(utterance);
            }
            console.log('Speech synthesis started');
        } else {
            console.log('Text-to-Speech not supported.');
            if (callback) callback();
        }
    }

    // Function to start the countdown and initiate recording
    function startCountdown(duration) {
        const countdownSpinner = document.getElementById('countdown-spinner');
        const countdownTimer = document.getElementById('countdown-timer');
        let timer = duration;

        countdownSpinner.style.display = 'block';
        countdownTimer.textContent = timer;

        const countdownInterval = setInterval(() => {
            timer--;
            if (timer <= 0) {
                clearInterval(countdownInterval);
                countdownSpinner.style.display = 'none';
                console.log('Countdown ended, starting recording');
                startRecording();
            } else {
                countdownTimer.textContent = timer;
            }
        }, 1000);
    }

    // Function to start recording audio (for transcription)
    async function startRecording() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            console.log('MediaRecorder started');

            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            microphone = audioContext.createMediaStreamSource(stream);

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstart = () => {
                document.getElementById("stop").disabled = false;
                document.getElementById("transcription").innerText = "Recording...";
                console.log('MediaRecorder onstart');
            };

            // Modified onstop callback for chunked upload
            mediaRecorder.onstop = async () => {
                document.getElementById("stop").disabled = true;
                document.getElementById("transcription").innerText = "Processing transcription...";
                console.log('MediaRecorder onstop');

                const blob = new Blob(audioChunks, { type: "audio/wav" });
                const url = URL.createObjectURL(blob);
                document.getElementById("player").src = url;

                audioChunks = [];

                // Generate a unique file ID and upload the audio in chunks
                const fileId = crypto.randomUUID();
                try {
                    await uploadAudioBlobInChunks(blob, fileId);
                } catch (error) {
                    console.error('Error in chunked audio upload:', error);
                    document.getElementById("transcription").innerText = "Error uploading audio.";
                    restartRecording();
                    return;
                }

                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    stream = null;
                }

                if (microphone) microphone.disconnect();
                if (audioContext) {
                    await audioContext.close();
                    audioContext = null;
                }
            };

            mediaRecorder.start();
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access your microphone. Please check permissions.');
        }
    }

    // Function to restart recording after silence is detected or empty transcription
    function restartRecording() {
        document.getElementById("transcription").innerText += "\nRestarting recording in 3 seconds...";
        console.log('Restarting recording in 3 seconds');

        stopRecordingResources();

        setTimeout(() => {
            document.getElementById("transcription").innerText = "Restarting recording...";
            startRecording();
        }, 3000);
    }

    // Function to stop and clean up recording resources for audio
    function stopRecordingResources() {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
        if (microphone) {
            microphone.disconnect();
            microphone = null;
        }
    }

    // Stop Recording (for audio) via the stop button
    document.getElementById("stop").onclick = () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            console.log('Stop button clicked, stopping MediaRecorder');
        }
    };

    // Submit Answer and Fetch Next Question
    async function submitAnswer() {
        if (!curr_transcription) {
            alert('No transcription available to submit.');
            return;
        }

        const forNextQuestion = {
            "candidate_answer": curr_transcription
        };

        document.getElementById("transcription").innerText += "\nSubmitting answer and fetching next question...";
        console.log('Submitting answer:', curr_transcription);

        try {
            const response = await fetch('/next_question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(forNextQuestion)
            });

            const data = await response.json();

            console.log('Next question data:', data);

            // If a connecting sentence is provided, speak it first and then display the next question.
            if (data.connecting_sentence) {
                console.log('Connecting sentence:', data.connecting_sentence);
                speakQuestion(data.connecting_sentence, () => {
                    if (data.interview_finished) {
                        endInterview();
                    } else if (data.question) {
                        displayQuestion(data.question.topic, data.question.question);
                    }
                });
            } else {
                if (data.interview_finished) {
                    speakQuestion("Thank you for taking the time to interview. We appreciate your interest in Vibgyor Group of Schools and will be in touch regarding the next steps soon.", ()=> {
                        endInterview();
                    });
                } else if (data.question) {
                    displayQuestion(data.question.topic, data.question.question);
                }
            }

            curr_transcription = "";
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while fetching the next question.');
        }
    }

    // Function to end the interview and perform cleanup
    async function endInterview() {
        try {
            interviewFinished = true;
            stopLocalStream();

            // Remove localVideo element if it exists
            if (localVideo?.parentNode) {
                localVideo.parentNode.removeChild(localVideo);
                console.log('localVideo element removed from the DOM');
            }

            // Toggle visibility of sections
            document.getElementById('interview-questions-section').style.display = 'none';
            document.getElementById('questions-list-section').style.display = 'block';

            // Fetch interview questions
            const questionsResponse = await fetch('/get_questions', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!questionsResponse.ok) {
                throw new Error(`Failed to fetch questions: ${questionsResponse.statusText}`);
            }

            const questionsData = await questionsResponse.json();

            if (questionsData.error) {
                alert(`Error: ${questionsData.error}`);
                return;
            }

            // Display questions and answers
            displayQuestions(questionsData.questions);

            // Calculate topic-wise average scores
            const topicAverages = calculateTopicAverages(questionsData.questions);

            // Prepare payload for ending the interview
            const payload = {
                questions: questionsData.questions.map(q => ({
                    topic: q.topic || '',
                    question: q.question || '',
                    answer: q.answer || '',
                    candi_answer: q.candi_answer || '',
                    category: q.category || '',
                    score: q.score || ''
                }))
            };

            // Send payload to end_interview endpoint
            const endInterviewResponse = await fetch('/end_interview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!endInterviewResponse.ok) {
                throw new Error(`Failed to end interview: ${endInterviewResponse.statusText}`);
            }

            const endData = await endInterviewResponse.json();

            // Display the summary
            displaySummary(endData.summary, topicAverages);
            console.log('Interview summary displayed');

        } catch (error) {
            console.error('Error ending interview:', error);
            alert('An error occurred while processing the interview termination.');
        }
    }

    // Helper function to display questions and answers
    function displayQuestions(questions) {
        const questionsList = document.getElementById('questions-list');
        questionsList.innerHTML = '';

        questions.forEach((q, index) => {
            const questionItem = document.createElement('div');
            questionItem.className = 'question-item';
            questionItem.innerHTML = `
            <strong>Question ${index + 1}:</strong> ${sanitizeHTML(q.question)}<br>
            <strong>Your Answer:</strong> ${sanitizeHTML(q.candi_answer) || 'No answer provided.'}<br>
            <strong>Category:</strong> ${sanitizeHTML(q.category) || 'N/A'}<br>
            <strong>Score:</strong> ${sanitizeHTML(q.score) || 'N/A'}
        `;
            questionsList.appendChild(questionItem);
        });
    }

    // Helper function to calculate topic-wise average scores
    function calculateTopicAverages(questions) {
        const topicScores = {};

        questions.forEach(q => {
            if (q.topic && q.score) {
                const score = parseFloat(q.score);
                if (!isNaN(score)) {
                    if (!topicScores[q.topic]) {
                        topicScores[q.topic] = { total: 0, count: 0 };
                    }
                    topicScores[q.topic].total += score;
                    topicScores[q.topic].count += 1;
                }
            }
        });

        return Object.entries(topicScores).map(([topic, { total, count }]) => ({
            topic,
            average: (total / count).toFixed(2)
        }));
    }
});


// Define subjects for each grade
const subjectsByGrade = {
    "Primary": ['', 'English', 'Mathematics', 'Science', 'Social Studies', 'Environmental Studies',
        'Hindi', 'Art and Craft', 'Physical Education'],

    "Secondary": ['', 'English', 'Mathematics', 'Science', 'Social Science', 'Hindi',
        'Art and Craft', 'Computer Science'],

    "Higher Secondary": ['', 'English', 'Mathematics', 'Physics', 'Chemistry', 'Biology',
        'Computer Science', 'Data Science', 'Engineering Graphics', 'Biotechnology',
        'Psychology', 'Accountancy', 'Economics', 'Entrepreneurship', 'Legal Studies',
        'Business Studies', 'History', 'Geography', 'Political Science', 'Sociology',
        'Philosophy', 'Fine Arts', 'Home Science']
};

document.addEventListener('DOMContentLoaded', function () {
    const gradeSelect = document.getElementById('grade');
    const subjectSelect = document.getElementById('subject_name');

    gradeSelect.addEventListener('change', function () {
        const selectedGrade = this.value;
        subjectSelect.innerHTML = '<option value="" disabled selected>Select your subject</option>';
        if (subjectsByGrade[selectedGrade]) {
            subjectsByGrade[selectedGrade].forEach(function (subject) {
                if (subject) {
                    const option = document.createElement('option');
                    option.value = subject;
                    option.textContent = subject;
                    subjectSelect.appendChild(option);
                }
            });
        }
    });
});
