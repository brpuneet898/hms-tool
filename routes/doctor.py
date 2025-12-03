"""
Doctor Routes for MediFriend
"""
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from routes.auth import role_required
from database import (
    get_doctor_appointments, update_appointment_status, get_doctor_patients,
    get_patient_details, create_prescription, create_notification, execute_query,
    get_user_notifications, get_unread_notification_count, mark_notifications_as_read,
    delete_read_notifications, get_doctor_stats
)
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
    
    return render_template('doctor_dashboard.html',
                         doctor_name=full_name,
                         doctor_id=user_id,
                         stats=stats)


@doctor_bp.route('/appointments')
@role_required('DOCTOR')
def appointments():
    """
    View doctor's appointments
    """
    user_id = session.get('user_id')
    appointments_list = get_doctor_appointments(user_id)
    
    return render_template('doctor_appointments.html', appointments=appointments_list)


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
        
        for name, dosage, duration in zip(medicine_names, medicine_dosages, medicine_durations):
            if name.strip() and dosage.strip() and duration.strip():
                medicines.append({
                    'name': name.strip(),
                    'dosage': dosage.strip(),
                    'duration': duration.strip()
                })
        
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
