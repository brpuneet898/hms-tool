from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os, base64, yaml, cv2, numpy as np
import google.generativeai as genai
import uuid
import json
from datetime import datetime

# Import configuration and routes
from config import Config
from routes.auth import auth_bp, login_required
from routes.patient import patient_bp
from routes.doctor import doctor_bp
from database import init_db, cleanup_old_notifications

# --------------------------------------------------
# ⚙️ Flask App Configuration
# --------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database on app startup
init_db()

# Cleanup old notifications (30+ days old)
try:
    cleanup_old_notifications()
    print("🧹 Cleaned up old notifications")
except:
    pass

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(patient_bp)
app.register_blueprint(doctor_bp)

# Add custom Jinja filter for JSON parsing
@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object"""
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except:
        return value

# Add custom Jinja filter for calculating age from date of birth
@app.template_filter('calculate_age')
def calculate_age_filter(dob_str):
    """Calculate age from date of birth string (YYYY-MM-DD)"""
    try:
        if not dob_str:
            return None
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        today = datetime.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except:
        return None

# Store chats in memory
chat_sessions = {}

# --------------------------------------------------
# 🔑 Configure Gemini API
# --------------------------------------------------
genai.configure(api_key=Config.GEMINI_API_KEY)

# Use Gemini Vision model
model = genai.GenerativeModel("gemini-2.5-pro")

# --------------------------------------------------
# 🔍 Prescription Extraction with Gemini
# --------------------------------------------------
def extract_prescription_from_image(image_data):
    """
    Extract prescription details from an image using Gemini AI.
    
    Args:
        image_data: Image bytes
    
    Returns:
        tuple: (extracted_data_dict, explanation_string)
    """
    try:
        # Create prompt for prescription extraction
        prompt = """Analyze this medical prescription image and extract the following details in JSON format:

{
  "doctor_name": "Full name of the prescribing doctor",
  "date": "Date of prescription (YYYY-MM-DD format)",
  "diagnosis": "Diagnosed condition or symptoms",
  "medicines": [
    {
      "name": "Medicine name",
      "dosage": "Dosage (e.g., 500mg, 2 tablets)",
      "duration": "Duration (e.g., 5 days, 2 weeks)"
    }
  ],
  "notes": "Any additional instructions or notes"
}

Important:
- If any field is not clearly visible or mentioned, use null or empty string
- Extract all medicines as a list with their details
- Format the date properly
- Return ONLY valid JSON, no additional text"""

        # Send to Gemini using same format as prescription reader
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ])
        
        # Parse response
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        extracted_data = json.loads(response_text)
        
        # Generate explanation
        explanation = f"Prescription processed successfully. Extracted {len(extracted_data.get('medicines', []))} medicine(s) from the image."
        
        return extracted_data, explanation
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response text: {response_text}")
        return None, f"Error parsing AI response: {str(e)}"
    except Exception as e:
        print(f"Prescription extraction error: {e}")
        return None, f"Error processing prescription: {str(e)}"

# --------------------------------------------------
# 🩺 Logo Helper
# --------------------------------------------------
def get_logo_data():
    img_path = os.path.join('static', 'images', 'medifriend_logo.png')
    if os.path.exists(img_path):
        with open(img_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded}"
    return None

# --------------------------------------------------
# 🏠 Routes
# --------------------------------------------------
@app.route('/')
def home():
    """Home page - shows different options based on login status"""
    if 'user_id' in session:
        # Redirect logged-in users to their dashboard
        if session.get('role') == 'DOCTOR':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))
    
    return render_template('index.html', logo_data=get_logo_data())


@app.route('/prescription-reader')
@login_required
def prescription_reader():
    """Prescription reader (requires login)"""
    return render_template('prescription_reader.html', logo_data=get_logo_data())

# --------------------------------------------------
# 🖼️ Image Enhancement Function
# --------------------------------------------------
def enhance_image(image_bytes):
    np_img = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image.")
    # Mild contrast enhancement only
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.equalizeHist(l)
    lab = cv2.merge((l, a, b))
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    _, buffer = cv2.imencode('.jpg', enhanced, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return buffer.tobytes()


# --------------------------------------------------
# 💬 Prescription Explanation via Gemini
# --------------------------------------------------
def explain_prescription_with_gemini(original_bytes, enhanced_bytes):
    prompt = """
    You are a medically trained assistant who reads handwritten prescriptions and explains them clearly to patients.

    Your task:
    - Carefully interpret the handwritten text from the prescription image.
    - Extract and organize all readable information, such as:
    • Patient details (if visible)
    • Doctor’s name or signature
    • Medicine names and formulations
    • Dosage and timing (e.g., 1-0-1, tid, after meals)
    • Any additional notes or instructions

    When writing your explanation:
    1. Be **accurate and complete** — include every detail that can be reasonably read.
    2. If a word, name, or medicine appears **misspelled or unclear**, but you can infer the correct one, write both — for example:  
    “Amoxcillin (likely meant Amoxicillin)”.
    3. Use **layman’s language** to describe what each medicine does and how it should be taken.
    4. **Do not critique or judge** the prescription or suggest alternatives — assume it’s prescribed by a qualified professional.
    5. Structure your answer clearly with sections or bullet points, similar to a detailed pharmacist’s explanation.
    6. End with: “Always follow your doctor’s advice before taking any medication.”

    Try to include every visible piece of readable text — even if minor — as part of the explanation.

    Be natural and helpful, but stay factual — like how you’d explain the prescription to a patient sitting in front of you.

    Start your response directly with the explanation. Do not include greetings or redundant introductions like 'Hello' or 'Of course' or 'Here is your explanation'. Just say any one only one time.
    """


    try:
        # Gemini handles multiple images — original and enhanced both
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": original_bytes},
            {"mime_type": "image/jpeg", "data": enhanced_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        return f"Error generating explanation: {str(e)}"


# --------------------------------------------------
# 🚀 API Endpoint
# --------------------------------------------------
@app.route('/process_prescription', methods=['POST'])
def process_prescription():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    image_bytes = file.read()

    try:
        # 1️⃣ Slightly enhance but keep image natural
        enhanced = enhance_image(image_bytes)

        # 2️⃣ Send both versions to Gemini for better interpretation
        explanation = explain_prescription_with_gemini(image_bytes, enhanced)

        return jsonify({"explanation": explanation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_chat_id():
    if 'chat_id' not in session:
        session['chat_id'] = str(uuid.uuid4())

        # Initialize chat with system prompt
        chat_sessions[session['chat_id']] = []

    return session['chat_id']


@app.route('/medical_chat', methods=['POST'])
def medical_chat():
    chat_id = session.get("chat_id")

    if not chat_id or chat_id not in chat_sessions:
        chat_id = str(uuid.uuid4())
        session['chat_id'] = chat_id
        chat_sessions[chat_id] = []   # NO SYSTEM PROMPT HERE (as you want)

    history = chat_sessions[chat_id]

    user_msg = request.json.get("message")
    if not user_msg:
        return jsonify({"error": "Message missing"}), 400

    # Add user message to history
    history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })


    # Ask Gemini
    model = genai.GenerativeModel("gemini-2.5-flash",
                                   system_instruction=(
                                        "You are MediFriend, a friendly, medically knowledgeable AI health assistant. "
                                        "Your job is to help users understand symptoms, medical terms, lab reports, prescriptions, "
                                        "treatments explained by their doctor, and general wellness guidance. "
                                        
                                        "You DO NOT diagnose medical conditions. "
                                        "However, based on common medical knowledge, you MAY explain the *most likely or common possible causes* "
                                        "of a symptom—but only when phrased carefully and conditionally, such as: "
                                        "'This could possibly be related to...', 'One common reason might be...', "
                                        "'Based on what you described, a likely explanation is...', "
                                        "and always follow such statements with a reminder like: "
                                        "'Please consult a qualified doctor to confirm, as I am only a medical assistant.' "
                                        
                                        "You NEVER prescribe medications, suggest specific drug names, or recommend dosages. "
                                        "You may explain how prescribed medications generally work or what they are commonly used for. "
                                        "You educate, guide, explain symptoms, lifestyle advice, and general wellness tips. "
                                        "Your tone must always be empathetic, supportive, calm, and easy to understand. "
                                        "Use simple patient-friendly language, avoid jargon unless explained, and keep answers clear and helpful. "
                                        "Always encourage users to consult a qualified doctor for medical decisions."

                                        "Always prioritize safety. For any severe symptoms (chest pain, difficulty breathing, fainting, bleeding, "
                                        "seizures, suicidal thoughts), immediately advise urgent medical attention. "
                                        
                                        "Keep answers concise but helpful."
                                        "Stay conversational, respectful, and non-alarming. "
                                        "Your purpose is to guide, educate, and support—not diagnose or treat."   
                                   )
                                )
    response = model.generate_content(history)
    bot_reply = response.text

    # Store bot reply
    history.append({
        "role": "model",
        "parts": [{"text": bot_reply}]
    })


    return jsonify({
        "reply": bot_reply
    })

@app.route('/reset_chat', methods=['POST'])
def reset_chat():
    chat_id = session.get('chat_id')
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]

    session.pop('chat_id', None)

    # Immediately start new session WITH system prompt
    new_id = get_chat_id()

    return jsonify({"status": "reset"})



@app.route('/medical_bot')
@login_required
def medical_bot():
    """Medical chatbot (requires login)"""
    logo_data = get_logo_data()
    return render_template('medical_bot.html', logo_data=logo_data)

# --------------------------------------------------
# 🏁 Run Flask App
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
