"""
Doctor Routes for MediFriend
"""
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, make_response
from routes.auth import role_required
from database import (
    get_doctor_appointments, update_appointment_status, get_doctor_patients,
    get_patient_details, create_prescription, create_notification, execute_query,
    get_user_notifications, get_unread_notification_count, mark_notifications_as_read,
    delete_read_notifications, get_doctor_stats, search_patients, mark_follow_up_required,
    mark_follow_up_complete, generate_ics_calendar, get_doctor_today_appointments
)
from scheduler import create_medication_reminder
import json

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')


@doctor_bp.route('/dashboard')
@role_required('DOCTOR')
def dashboard():
    """
    Doctor dashboard - main hub
    """
    user_id = session.get('user_id')
    full_name = session.get('full_name')
    
    # Get statistics
    stats = get_doctor_stats(user_id)
    
    # Get today's appointments
    today_appointments = get_doctor_today_appointments(user_id)
    
    return render_template('doctor_dashboard.html',
                         doctor_name=full_name,
                         doctor_id=user_id,
                         stats=stats,
                         today_appointments=today_appointments)


@doctor_bp.route('/appointments')
@role_required('DOCTOR')
def appointments():
    """
    View doctor's appointments
    """
    from datetime import datetime
    user_id = session.get('user_id')
    appointments_list = get_doctor_appointments(user_id)
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Check which appointments have summaries
    appointment_ids = [apt['id'] for apt in appointments_list]
    summaries_dict = {}
    if appointment_ids:
        placeholders = ','.join('?' * len(appointment_ids))
        summary_query = f"""
            SELECT appointment_id
            FROM appointment_summaries
            WHERE appointment_id IN ({placeholders})
        """
        summaries = execute_query(summary_query, tuple(appointment_ids), fetchall=True)
        summaries_dict = {s['appointment_id']: True for s in summaries}
    
    # Add has_summary flag to each appointment
    for apt in appointments_list:
        apt['has_summary'] = apt['id'] in summaries_dict
    
    return render_template('doctor_appointments.html', 
                         appointments=appointments_list,
                         current_datetime=current_datetime)


@doctor_bp.route('/appointment/accept/<int:appointment_id>', methods=['POST'])
@role_required('DOCTOR')
def accept_appointment(appointment_id):
    """
    Accept/confirm an appointment
    """
    try:
        # Get appointment details to notify patient
        query = "SELECT patient_id, date, time FROM appointments WHERE id = ?"
        appointment = execute_query(query, (appointment_id,), fetchone=True)
        
        update_appointment_status(appointment_id, 'CONFIRMED')
        
        # Create notification for patient
        doctor_name = session.get('full_name', 'Doctor')
        message = f"Dr. {doctor_name} accepted your appointment for {appointment['date']} at {appointment['time']}"
        create_notification(
            user_id=appointment['patient_id'],
            notification_type='APPOINTMENT_ACCEPTED',
            message=message,
            link='/patient/appointments',
            appointment_id=appointment_id
        )
        
        flash('Appointment confirmed successfully!', 'success')
    except Exception as e:
        flash(f'Error confirming appointment: {str(e)}', 'danger')
    
    return redirect(url_for('doctor.appointments'))


@doctor_bp.route('/appointment/reject/<int:appointment_id>', methods=['POST'])
@role_required('DOCTOR')
def reject_appointment(appointment_id):
    """
    Reject an appointment
    """
    try:
        # Get appointment details to notify patient
        query = "SELECT patient_id, date, time FROM appointments WHERE id = ?"
        appointment = execute_query(query, (appointment_id,), fetchone=True)
        
        update_appointment_status(appointment_id, 'REJECTED')
        
        # Create notification for patient (no link for rejected appointments)
        doctor_name = session.get('full_name', 'Doctor')
        message = f"Dr. {doctor_name} declined your appointment request for {appointment['date']} at {appointment['time']}"
        create_notification(
            user_id=appointment['patient_id'],
            notification_type='APPOINTMENT_REJECTED',
            message=message,
            link=None,
            appointment_id=appointment_id
        )
        
        flash('Appointment rejected.', 'info')
    except Exception as e:
        flash(f'Error rejecting appointment: {str(e)}', 'danger')
    
    return redirect(url_for('doctor.appointments'))


@doctor_bp.route('/appointment/reschedule/<int:appointment_id>', methods=['POST'])
@role_required('DOCTOR')
def reschedule_appointment(appointment_id):
    """
    Reschedule an appointment to a new date and time
    """
    try:
        new_date = request.form.get('new_date')
        new_time = request.form.get('new_time')
        
        if not new_date or not new_time:
            flash('Please provide both date and time for rescheduling', 'warning')
            return redirect(url_for('doctor.appointments'))
        
        # Get current appointment details
        query = "SELECT patient_id, date, time FROM appointments WHERE id = ?"
        appointment = execute_query(query, (appointment_id,), fetchone=True)
        
        # Update appointment with reschedule info
        update_query = """
            UPDATE appointments 
            SET date = ?, time = ?, status = 'CONFIRMED', 
                was_rescheduled = 1, original_date = ?, original_time = ?
            WHERE id = ?
        """
        execute_query(update_query, (new_date, new_time, appointment['date'], appointment['time'], appointment_id), commit=True)
        
        # Create notification for patient
        doctor_name = session.get('full_name', 'Doctor')
        message = f"Dr. {doctor_name} rescheduled and accepted your appointment to {new_date} at {new_time}"
        create_notification(
            user_id=appointment['patient_id'],
            notification_type='APPOINTMENT_ACCEPTED',
            message=message,
            link='/patient/appointments',
            appointment_id=appointment_id
        )
        
        flash(f'Appointment rescheduled successfully to {new_date} at {new_time}', 'success')
    except Exception as e:
        flash(f'Error rescheduling appointment: {str(e)}', 'danger')
    
    return redirect(url_for('doctor.appointments'))


@doctor_bp.route('/appointment/complete/<int:appointment_id>', methods=['POST'])
@role_required('DOCTOR')
def complete_appointment(appointment_id):
    """
    Mark appointment as completed
    """
    try:
        update_appointment_status(appointment_id, 'COMPLETED')
        flash('Appointment marked as completed!', 'success')
    except Exception as e:
        flash(f'Error completing appointment: {str(e)}', 'danger')
    
    return redirect(url_for('doctor.appointments'))


@doctor_bp.route('/patients')
@role_required('DOCTOR')
def patients():
    """
    View doctor's patients
    """
    user_id = session.get('user_id')
    patients_list = get_doctor_patients(user_id)
    
    return render_template('doctor_patients.html', patients=patients_list)


@doctor_bp.route('/write-prescription/<int:patient_id>/<int:appointment_id>', methods=['GET', 'POST'])
@role_required('DOCTOR')
def write_prescription(patient_id, appointment_id):
    """
    Write prescription for patient
    """
    doctor_id = session.get('user_id')
    
    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Collect medicines from dynamic form fields
        medicines = []
        medicine_names = request.form.getlist('medicine_name[]')
        medicine_dosages = request.form.getlist('medicine_dosage[]')
        medicine_durations = request.form.getlist('medicine_duration[]')
        medicine_frequencies = request.form.getlist('medicine_frequency[]')
        medicine_foods = request.form.getlist('medicine_food[]')
        
        # Get timing checkboxes (they may have different array lengths)
        medicine_timing_morning = request.form.getlist('medicine_timing_morning[]')
        medicine_timing_afternoon = request.form.getlist('medicine_timing_afternoon[]')
        medicine_timing_evening = request.form.getlist('medicine_timing_evening[]')
        medicine_timing_night = request.form.getlist('medicine_timing_night[]')
        
        for idx, (name, dosage, duration) in enumerate(zip(medicine_names, medicine_dosages, medicine_durations)):
            if name.strip() and dosage.strip() and duration.strip():
                # Build timing array based on checkboxes
                timing = []
                if idx < len(medicine_timing_morning) and medicine_timing_morning[idx]:
                    timing.append('Morning')
                if idx < len(medicine_timing_afternoon) and medicine_timing_afternoon[idx]:
                    timing.append('Afternoon')
                if idx < len(medicine_timing_evening) and medicine_timing_evening[idx]:
                    timing.append('Evening')
                if idx < len(medicine_timing_night) and medicine_timing_night[idx]:
                    timing.append('Night')
                
                medicine_data = {
                    'name': name.strip(),
                    'dosage': dosage.strip(),
                    'duration': duration.strip() + ' days'
                }
                
                # Add frequency if selected
                if idx < len(medicine_frequencies) and medicine_frequencies[idx]:
                    medicine_data['frequency'] = medicine_frequencies[idx]
                
                # Add timing if selected
                if timing:
                    medicine_data['timing'] = ', '.join(timing)
                
                # Add food relation if selected
                if idx < len(medicine_foods) and medicine_foods[idx]:
                    food_map = {
                        'before_food': 'Before food',
                        'after_food': 'After food',
                        'with_food': 'With food',
                        'empty_stomach': 'Empty stomach',
                        'anytime': 'Anytime'
                    }
                    medicine_data['food'] = food_map.get(medicine_foods[idx], medicine_foods[idx])
                
                medicines.append(medicine_data)
        
        if not diagnosis:
            flash('Diagnosis is required', 'error')
            return redirect(url_for('doctor.write_prescription', 
                                   patient_id=patient_id, 
                                   appointment_id=appointment_id))
        
        # Convert medicines to JSON (empty array if no medicines)
        medicines_json = json.dumps(medicines)
        
        # Create prescription
        prescription_id = create_prescription(
            doctor_id=doctor_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            diagnosis=diagnosis,
            medicines_json=medicines_json,
            notes=notes if notes else None
        )
        
        if prescription_id:
            # Create notification for patient
            doctor_name = session.get('full_name', 'Doctor')
            message = f"Dr. {doctor_name} has written a prescription for you"
            create_notification(
                user_id=patient_id,
                notification_type='PRESCRIPTION_WRITTEN',
                message=message,
                link='/patient/prescriptions',
                prescription_id=prescription_id
            )
            
            # Create medication reminder if there are medicines with durations
            try:
                if medicines:
                    # Get max duration from all medicines
                    max_duration = 0
                    for med in medicines:
                        duration_str = med.get('duration', '0 days')
                        # Extract number from "30 days"
                        duration_days = int(duration_str.split()[0]) if duration_str.split()[0].isdigit() else 0
                        max_duration = max(max_duration, duration_days)
                    
                    if max_duration > 0:
                        create_medication_reminder(prescription_id, patient_id, max_duration)
                        print(f"✅ Created medication reminder for prescription {prescription_id} ({max_duration} days)")
            except Exception as e:
                print(f"⚠️ Failed to create medication reminder: {e}")
            
            flash('Prescription created successfully', 'success')
            return redirect(url_for('doctor.appointments'))
        else:
            flash('Failed to create prescription', 'error')
            return redirect(url_for('doctor.write_prescription', 
                                   patient_id=patient_id, 
                                   appointment_id=appointment_id))
    
    # GET request - show form
    patient = get_patient_details(patient_id)
    if not patient:
        flash('Patient not found', 'error')
        return redirect(url_for('doctor.appointments'))
    
    return render_template('write_prescription.html', 
                          patient=patient, 
                          appointment_id=appointment_id)


# --------------------------------------------------
# 📬 Notification API Routes
# --------------------------------------------------

@doctor_bp.route('/api/notifications', methods=['GET'])
@role_required('DOCTOR')
def get_notifications():
    """
    Get all unread notifications for the current doctor
    """
    user_id = session.get('user_id')
    notifications = get_user_notifications(user_id, unread_only=True)
    return jsonify({'success': True, 'notifications': notifications})


@doctor_bp.route('/api/notifications/count', methods=['GET'])
@role_required('DOCTOR')
def get_notification_count():
    """
    Get count of unread notifications
    """
    user_id = session.get('user_id')
    count = get_unread_notification_count(user_id)
    return jsonify({'success': True, 'count': count})


@doctor_bp.route('/api/notifications/mark-read', methods=['POST'])
@role_required('DOCTOR')
def mark_notifications_read():
    """
    Mark all notifications as read and delete them
    """
    user_id = session.get('user_id')
    mark_notifications_as_read(user_id)
    delete_read_notifications(user_id)
    return jsonify({'success': True})


@doctor_bp.route('/api/search-patients', methods=['GET'])
@role_required('DOCTOR')
def api_search_patients():
    """
    AJAX endpoint for searching patients
    Returns JSON results for live search
    """
    query = request.args.get('q', '').strip()
    doctor_id = session.get('user_id')
    
    if not query or len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short', 'patients': []})
    
    try:
        # Search only this doctor's patients
        patients = search_patients(query, doctor_id)
        
        # Format results for frontend
        results = [{
            'id': patient['id'],
            'name': patient['full_name'],
            'email': patient['email'],
            'phone': patient['phone'] or 'N/A',
            'gender': patient['gender'] or 'N/A',
            'blood_group': patient['blood_group'] or 'N/A'
        } for patient in patients]
        
        return jsonify({
            'success': True,
            'count': len(results),
            'patients': results
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'patients': []})


@doctor_bp.route('/api/patient-details/<int:patient_id>', methods=['GET'])
@role_required('DOCTOR')
def api_patient_details(patient_id):
    """
    AJAX endpoint for comprehensive patient details
    Returns all patient information including vitals, prescriptions from all doctors, etc.
    """
    try:
        # Get comprehensive patient data
        from database import get_comprehensive_patient_details
        patient_data = get_comprehensive_patient_details(patient_id)
        
        if not patient_data:
            return jsonify({'success': False, 'message': 'Patient not found'})
        
        return jsonify({
            'success': True,
            'patient': patient_data
        })
    
    except Exception as e:
        print(f"Error fetching patient details: {e}")
        return jsonify({'success': False, 'message': str(e)})


@doctor_bp.route('/schedule-follow-up', methods=['POST'])
@role_required('DOCTOR')
def schedule_follow_up():
    """
    Mark appointment as requiring follow-up and schedule suggested date
    """
    try:
        appointment_id = request.form.get('appointment_id')
        follow_up_date = request.form.get('follow_up_date')
        follow_up_notes = request.form.get('follow_up_notes', '').strip()
        
        if not appointment_id or not follow_up_date:
            flash('Missing required information', 'error')
            return redirect(url_for('doctor.appointments'))
        
        doctor_id = session.get('user_id')
        
        # Get patient_id from appointment
        query = "SELECT patient_id FROM appointments WHERE id = ?"
        result = execute_query(query, (appointment_id,), fetchone=True)
        
        if not result:
            flash('Appointment not found', 'error')
            return redirect(url_for('doctor.appointments'))
        
        patient_id = result['patient_id']
        
        # Mark follow-up required and create notification
        mark_follow_up_required(appointment_id, follow_up_date, doctor_id, patient_id)
        
        # Update appointment with follow-up notes if provided
        if follow_up_notes:
            update_query = "UPDATE appointments SET notes = ? WHERE id = ?"
            execute_query(update_query, (follow_up_notes, appointment_id))
        
        flash(f'Follow-up scheduled successfully for {follow_up_date}', 'success')
        return redirect(url_for('doctor.appointments'))
        
    except Exception as e:
        flash(f'Error scheduling follow-up: {str(e)}', 'error')
        return redirect(url_for('doctor.appointments'))

@doctor_bp.route('/mark-follow-up-complete/<int:appointment_id>')
@role_required('DOCTOR')
def complete_follow_up(appointment_id):
    """
    Mark a follow-up as complete
    """
    try:
        mark_follow_up_complete(appointment_id)
        flash('Follow-up marked as complete', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('doctor.appointments'))


@doctor_bp.route('/download-calendar/<int:appointment_id>')
@role_required('DOCTOR')
def download_calendar(appointment_id):
    """Download .ics calendar file for appointment"""
    doctor_id = session.get('user_id')
    
    # Get appointment details
    query = """
        SELECT a.*, 
               u.full_name as patient_name,
               dd.clinic_address
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.id = ? AND a.doctor_id = ?
    """
    appointment = execute_query(query, (appointment_id, doctor_id), fetchone=True)
    
    if not appointment:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('doctor.appointments'))
    
    # Generate .ics content
    ics_content = generate_ics_calendar({
        'patient_name': appointment['patient_name'],
        'doctor_name': session.get('full_name'),
        'date': appointment['date'],
        'time': appointment['time'],
        'consultation_mode': appointment['consultation_mode'],
        'meet_link': appointment.get('meet_link'),
        'clinic_address': appointment.get('clinic_address'),
        'symptoms': appointment.get('symptoms')
    })
    
    # Create response with .ics file
    response = make_response(ics_content)
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=appointment_{appointment_id}.ics'
    
    return response


@doctor_bp.route('/appointment/generate-summary-audio', methods=['POST'])
@role_required('DOCTOR')
def generate_summary_audio():
    """
    Generate AI summary from audio recording using Gemini's audio capabilities
    No FFmpeg, Whisper, or Pyannote needed - fully portable!
    """
    try:
        import google.generativeai as genai
        from config import Config
        import tempfile
        import os
        import base64
        
        # Get uploaded audio file
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'No audio file uploaded'}), 400
        
        audio_file = request.files['audio']
        appointment_id = request.form.get('appointment_id')
        
        if not appointment_id:
            return jsonify({'success': False, 'error': 'Missing appointment_id'}), 400
        
        # Read audio data
        audio_data = audio_file.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        print(f"🎙️ Processing audio with Gemini... ({len(audio_data)} bytes)")
        
        # Configure Gemini
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Create audio part for Gemini
        audio_part = {
            "inline_data": {
                "mime_type": "audio/webm",
                "data": audio_base64
            }
        }
        
        prompt = """You are a medical documentation assistant. Listen to this doctor-patient consultation recording.

Your tasks:
1. Transcribe the conversation
2. Identify who is speaking (doctor vs patient) based on context and voice
3. Create a detailed narrative summary

Provide your response in the following JSON format:
{
    "transcription": "Full transcription with speaker labels like [DOCTOR]: ... [PATIENT]: ...",
    "discussions": "Narrative of the consultation flow - e.g., 'The patient complained of headaches for 3 days. The doctor asked about fever and severity. The patient confirmed mild fever...'",
    "symptoms": "All symptoms mentioned by the patient during the consultation",
    "diagnosis": "The doctor's diagnosis or medical assessment",
    "recommendations": "What the doctor prescribed or recommended - medications, lifestyle changes, follow-up instructions",
    "additional_notes": "Any other important information, warnings, or special instructions given"
}

Guidelines:
1. Write 'discussions' as a flowing narrative showing the conversation
2. Use phrases like "The patient reported...", "The doctor diagnosed...", "The doctor prescribed..."
3. Identify speakers by context (patient describes symptoms, doctor asks questions/diagnoses)
4. Only include information actually present in the audio
5. Be medically accurate and professional
6. Return ONLY valid JSON, no extra text

JSON Summary:"""
        
        # Send audio + prompt to Gemini
        response = model.generate_content([prompt, audio_part])
        summary_text = response.text.strip()
        
        print(f"📝 Gemini response received")
        
        # Clean markdown
        if summary_text.startswith('```json'):
            summary_text = summary_text[7:]
        if summary_text.startswith('```'):
            summary_text = summary_text[3:]
        if summary_text.endswith('```'):
            summary_text = summary_text[:-3]
        summary_text = summary_text.strip()
        
        # Parse JSON
        summary_json = json.loads(summary_text)
        
        # Log transcription for debugging
        if 'transcription' in summary_json:
            print(f"\n📝 Transcription:\n{summary_json['transcription']}\n")
        
        # Store in database (without transcription field for storage)
        storage_json = {k: v for k, v in summary_json.items() if k != 'transcription'}
        
        insert_query = """
            INSERT INTO appointment_summaries (appointment_id, summary_json)
            VALUES (?, ?)
        """
        execute_query(insert_query, (appointment_id, json.dumps(storage_json)), commit=True)
        
        return jsonify({'success': True, 'summary': storage_json})
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@doctor_bp.route('/appointment/generate-summary', methods=['POST'])
@role_required('DOCTOR')
def generate_summary():
    """
    Generate AI summary from voice transcription using Gemini (Web Speech API text input)
    Gemini analyzes the raw text to identify speakers based on context
    """
    try:
        import google.generativeai as genai
        from config import Config
        
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        transcription = data.get('transcription')
        
        if not appointment_id or not transcription:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Print FULL raw transcription for debugging
        print("\n" + "="*60)
        print("📝 RAW TRANSCRIPTION FROM WEB SPEECH API:")
        print("="*60)
        print(transcription)
        print("="*60)
        print(f"Total length: {len(transcription)} characters")
        print("="*60 + "\n")
        
        # Configure Gemini
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""You are a medical documentation assistant. Analyze this doctor-patient consultation transcription.

Raw Transcription (from speech-to-text):
{transcription}

Your task is to identify who said what based on context clues:
- The PATIENT typically: complains about symptoms, describes pain/discomfort, answers questions about their condition
- The DOCTOR typically: asks diagnostic questions, provides medical advice, makes diagnoses, prescribes treatments

Then create a detailed narrative summary that captures the flow of the consultation.

Provide your response in the following JSON format:
{{
    "discussions": "Narrative of the consultation flow - e.g., 'The patient complained of headaches for 3 days. The doctor asked about fever and severity. The patient confirmed mild fever...'",
    "symptoms": "All symptoms mentioned by the patient during the consultation",
    "diagnosis": "The doctor's diagnosis or medical assessment",
    "recommendations": "What the doctor prescribed or recommended - medications, lifestyle changes, follow-up instructions",
    "additional_notes": "Any other important information, warnings, or special instructions given"
}}

Guidelines:
1. Infer who is speaking (doctor vs patient) from context - don't worry if you're not 100% certain
2. Write 'discussions' as a flowing narrative showing the conversation
3. Use phrases like "The patient reported...", "The doctor diagnosed...", "The doctor prescribed..."
4. Only include information actually present in the transcript
5. Be medically accurate and professional
6. Return ONLY valid JSON, no extra text

JSON Summary:"""
        
        response = model.generate_content(prompt)
        summary_text = response.text.strip()
        
        # Clean markdown formatting
        if summary_text.startswith('```json'):
            summary_text = summary_text[7:]
        if summary_text.startswith('```'):
            summary_text = summary_text[3:]
        if summary_text.endswith('```'):
            summary_text = summary_text[:-3]
        summary_text = summary_text.strip()
        
        # Parse JSON response
        summary_json = json.loads(summary_text)
        
        # Store in database
        insert_query = """
            INSERT INTO appointment_summaries (appointment_id, summary_json)
            VALUES (?, ?)
        """
        execute_query(insert_query, (appointment_id, json.dumps(summary_json)), commit=True)
        
        return jsonify({'success': True, 'message': 'Summary generated successfully'})
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@doctor_bp.route('/appointment/get-summary/<int:appointment_id>')
@role_required('DOCTOR')
def get_summary(appointment_id):
    """
    Retrieve summary for an appointment
    """
    try:
        query = """
            SELECT summary_json, created_at
            FROM appointment_summaries
            WHERE appointment_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = execute_query(query, (appointment_id,), fetchone=True)
        
        if result:
            return jsonify({
                'success': True,
                'summary': json.loads(result['summary_json']),
                'created_at': result['created_at']
            })
        else:
            return jsonify({'success': False, 'error': 'No summary found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
