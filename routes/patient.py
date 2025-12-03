"""
Patient Routes for MediFriend
"""
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from routes.auth import role_required
from database import (
    get_all_doctors, create_appointment, get_patient_appointments,
    cancel_appointment, get_patient_prescriptions,
    create_uploaded_prescription, get_patient_uploaded_prescriptions,
    delete_uploaded_prescription as db_delete_uploaded_prescription,
    get_user_notifications, get_unread_notification_count, mark_notifications_as_read,
    delete_read_notifications
)
from datetime import date
import os
import json
import base64

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')


@patient_bp.route('/dashboard')
@role_required('PATIENT')
def dashboard():
    """
    Patient dashboard - main hub
    """
    user_id = session.get('user_id')
    full_name = session.get('full_name')
    
    return render_template('patient_dashboard.html', 
                         user_name=full_name,
                         user_id=user_id)


@patient_bp.route('/appointments')
@role_required('PATIENT')
def appointments():
    """
    View patient's appointments (excluding rejected ones)
    """
    user_id = session.get('user_id')
    all_appointments = get_patient_appointments(user_id)
    
    # Filter out rejected appointments
    appointments_list = [apt for apt in all_appointments if apt['status'] != 'REJECTED']
    
    return render_template('patient_appointments.html', 
                         appointments=appointments_list)


@patient_bp.route('/book-appointment', methods=['GET', 'POST'])
@role_required('PATIENT')
def book_appointment():
    """
    Book new appointment
    """
    if request.method == 'POST':
        patient_id = session.get('user_id')
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('date')
        appointment_time = request.form.get('time')
        symptoms = request.form.get('symptoms', '').strip()
        
        # Validation
        if not doctor_id or not appointment_date or not appointment_time:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('patient.book_appointment'))
        
        try:
            # Create appointment
            appointment_id = create_appointment(
                patient_id=patient_id,
                doctor_id=int(doctor_id),
                date=appointment_date,
                time=appointment_time,
                symptoms=symptoms if symptoms else None
            )
            
            flash('Appointment booked successfully! Waiting for doctor confirmation.', 'success')
            return redirect(url_for('patient.appointments'))
            
        except Exception as e:
            flash(f'Error booking appointment: {str(e)}', 'danger')
            return redirect(url_for('patient.book_appointment'))
    
    # GET request - show booking form
    doctors = get_all_doctors()
    today = date.today().isoformat()
    
    return render_template('book_appointment.html', 
                         doctors=doctors,
                         today=today)


@patient_bp.route('/cancel-appointment/<int:appointment_id>', methods=['POST'])
@role_required('PATIENT')
def cancel_appointment_route(appointment_id):
    """
    Cancel an appointment
    """
    try:
        cancel_appointment(appointment_id)
        flash('Appointment cancelled successfully.', 'success')
    except Exception as e:
        flash(f'Error cancelling appointment: {str(e)}', 'danger')
    
    return redirect(url_for('patient.appointments'))


@patient_bp.route('/prescriptions')
@role_required('PATIENT')
def prescriptions():
    """
    View patient's prescriptions (both doctor-written and uploaded)
    """
    user_id = session.get('user_id')
    
    # Get doctor-written prescriptions
    prescriptions_list = get_patient_prescriptions(user_id)
    
    # Get uploaded prescriptions
    uploaded_prescriptions_list = get_patient_uploaded_prescriptions(user_id)
    
    return render_template('patient_prescriptions.html',
                         prescriptions=prescriptions_list,
                         uploaded_prescriptions=uploaded_prescriptions_list)


@patient_bp.route('/upload-prescription-api', methods=['POST'])
@role_required('PATIENT')
def upload_prescription_api():
    """
    API endpoint to upload and process prescription image
    """
    try:
        user_id = session.get('user_id')
        
        # Check if file is present
        if 'prescription_image' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['prescription_image']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read file data
        file_data = file.read()
        
        # Import extraction function from app
        from app import extract_prescription_from_image
        
        # Extract data using Gemini
        extracted_data, explanation = extract_prescription_from_image(file_data)
        
        if extracted_data is None:
            return jsonify({'success': False, 'error': explanation}), 500
        
        # Save to database
        create_uploaded_prescription(
            patient_id=user_id,
            filename=file.filename,
            extracted_data=json.dumps(extracted_data),
            explanation=explanation
        )
        
        return jsonify({'success': True, 'message': 'Prescription uploaded successfully'})
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@patient_bp.route('/delete-uploaded-prescription/<int:upload_id>', methods=['POST'])
@role_required('PATIENT')
def delete_uploaded_prescription(upload_id):
    """
    Delete an uploaded prescription
    """
    try:
        db_delete_uploaded_prescription(upload_id)
        flash('Prescription deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting prescription: {str(e)}', 'danger')
    
    return redirect(url_for('patient.prescriptions'))


@patient_bp.route('/upload-prescription')
@role_required('PATIENT')
def upload_prescription():
    """
    Upload handwritten prescription for AI reading
    """
    # TODO: Link to existing prescription reader
    return render_template('upload_prescription.html')


# --------------------------------------------------
# 📬 Notification API Routes
# --------------------------------------------------

@patient_bp.route('/api/notifications', methods=['GET'])
@role_required('PATIENT')
def get_notifications():
    """
    Get all unread notifications for the current patient
    """
    user_id = session.get('user_id')
    notifications = get_user_notifications(user_id, unread_only=True)
    return jsonify({'success': True, 'notifications': notifications})


@patient_bp.route('/api/notifications/count', methods=['GET'])
@role_required('PATIENT')
def get_notification_count():
    """
    Get count of unread notifications
    """
    user_id = session.get('user_id')
    count = get_unread_notification_count(user_id)
    return jsonify({'success': True, 'count': count})


@patient_bp.route('/api/notifications/mark-read', methods=['POST'])
@role_required('PATIENT')
def mark_notifications_read():
    """
    Mark all notifications as read and delete them
    """
    user_id = session.get('user_id')
    mark_notifications_as_read(user_id)
    delete_read_notifications(user_id)
    return jsonify({'success': True})
