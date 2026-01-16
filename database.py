"""
Database Connection and Initialization for MediFriend
"""
import sqlite3
import os
from datetime import date, datetime, timedelta, timezone
import secrets
import string
import json
from models import ALL_MODELS

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current datetime in IST"""
    return datetime.now(IST)

def get_ist_today():
    """Get current date in IST"""
    return get_ist_now().date()


DB_PATH = os.path.join(os.path.dirname(__file__), 'hms.db')


def get_db_connection():
    """
    Get a new database connection with row factory for dictionary-like access
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initialize the database by creating all tables from models.
    Only creates database if it doesn't exist.
    """
    # Check if database already exists
    if os.path.exists(DB_PATH):
        print(f"✅ Database already exists at: {DB_PATH}")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🏥 Initializing MediFriend Database...")
    
    try:
        # Create all tables
        for model in ALL_MODELS:
            print(f"   Creating table: {model.TABLE_NAME}")
            cursor.execute(model.create_table_sql())
            
            # Create indexes if available
            if hasattr(model, 'create_indexes_sql'):
                for index_sql in model.create_indexes_sql():
                    cursor.execute(index_sql)
        
        conn.commit()
        print("✅ Database initialized successfully!")
        print(f"📁 Database location: {DB_PATH}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    """
    Helper function to execute SQL queries
    
    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetchone: Return single row
        fetchall: Return all rows
        commit: Commit changes (for INSERT/UPDATE/DELETE)
    
    Returns:
        Query results or lastrowid for INSERT operations
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
            return cursor.lastrowid
        
        if fetchone:
            result = cursor.fetchone()
            return dict(result) if result else None
        
        if fetchall:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        
        return None
        
    except Exception as e:
        if commit:
            conn.rollback()
        raise e
    finally:
        conn.close()


def generate_meet_link():
    """
    Generate a unique Jitsi Meet link for online consultations
    Jitsi Meet is free and works without API keys
    Format: https://meet.jit.si/MediFriend-xxxxx (random 12-char code)
    """
    # Generate random string of 12 characters (letters + numbers)
    chars = string.ascii_lowercase + string.digits
    code = ''.join(secrets.choice(chars) for _ in range(12))
    
    # Use Jitsi Meet - free and works immediately without any setup
    # Format: MediFriend-{random_code} to make room names unique
    return f"https://meet.jit.si/MediFriend-{code}"


def generate_ics_calendar(appointment_data):
    """
    Generate iCalendar (.ics) file content for appointment
    Works with Google Calendar, Outlook, Apple Calendar, etc.
    
    Args:
        appointment_data: dict with keys: patient_name, doctor_name, date, time, 
                         consultation_mode, meet_link, clinic_address, symptoms
    
    Returns:
        str: iCalendar format content
    """
    # Parse appointment date and time
    appointment_datetime = datetime.strptime(
        f"{appointment_data['date']} {appointment_data['time']}", 
        "%Y-%m-%d %H:%M"
    )
    
    # Calculate end time (assume 30 min consultation)
    from datetime import timedelta
    end_datetime = appointment_datetime + timedelta(minutes=30)
    
    # Format dates in iCalendar format (YYYYMMDDTHHMMSS)
    dtstart = appointment_datetime.strftime("%Y%m%dT%H%M%S")
    dtend = end_datetime.strftime("%Y%m%dT%H%M%S")
    dtstamp = get_ist_now().strftime("%Y%m%dT%H%M%S")
    
    # Generate unique ID
    uid = f"{secrets.token_hex(8)}@medifriend.com"
    
    # Build description with meet link or clinic address
    if appointment_data['consultation_mode'] == 'ONLINE':
        location = "Online Video Consultation"
        description = f"Online consultation via Jitsi Meet\\n\\nJoin Link: {appointment_data['meet_link']}"
        if appointment_data.get('symptoms'):
            description += f"\\n\\nSymptoms: {appointment_data['symptoms']}"
    else:
        location = appointment_data.get('clinic_address', 'Clinic')
        description = f"Physical consultation at clinic\\n\\nAddress: {location}"
        if appointment_data.get('symptoms'):
            description += f"\\n\\nSymptoms: {appointment_data['symptoms']}"
    
    # Build iCalendar content
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//MediFriend//Healthcare Management System//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:Medical Consultation - Dr. {appointment_data['doctor_name']}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
    
    return ics_content


def insert_user(full_name, email, password_hash, role, phone=None, gender=None, dob=None):
    """
    Insert a new user into the database
    """
    query = """
        INSERT INTO users (full_name, email, password_hash, role, phone, gender, dob)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (full_name, email, password_hash, role, phone, gender, dob), commit=True)


def get_user_by_email(email):
    """
    Get user by email
    """
    query = "SELECT * FROM users WHERE email = ?"
    return execute_query(query, (email,), fetchone=True)


def get_user_by_id(user_id):
    """
    Get user by ID
    """
    query = "SELECT * FROM users WHERE id = ?"
    return execute_query(query, (user_id,), fetchone=True)


def insert_patient_details(user_id, blood_group=None, allergies=None, chronic_conditions=None, emergency_contact=None):
    """
    Insert patient-specific details
    """
    query = """
        INSERT INTO patient_details (user_id, blood_group, allergies, chronic_conditions, emergency_contact)
        VALUES (?, ?, ?, ?, ?)
    """
    return execute_query(query, (user_id, blood_group, allergies, chronic_conditions, emergency_contact), commit=True)


def insert_doctor_details(user_id, specialization, qualification=None, experience_years=0, consultation_fee=0.0, schedule_json=None, clinic_address=None, latitude=None, longitude=None, consultation_modes='PHYSICAL'):
    """
    Insert doctor-specific details
    """
    query = """
        INSERT INTO doctor_details (user_id, specialization, qualification, experience_years, consultation_fee, schedule_json, clinic_address, latitude, longitude, consultation_modes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (user_id, specialization, qualification, experience_years, consultation_fee, schedule_json, clinic_address, latitude, longitude, consultation_modes), commit=True)


def get_all_doctors():
    """
    Get all doctors with their details including ratings
    """
    query = """
        SELECT u.*, d.specialization, d.experience_years, d.consultation_fee,
               d.average_rating, d.total_ratings, d.clinic_address, d.latitude, d.longitude, d.consultation_modes, d.qualification
        FROM users u
        JOIN doctor_details d ON u.id = d.user_id
        WHERE u.role = 'DOCTOR'
        ORDER BY d.average_rating DESC, u.full_name
    """
    return execute_query(query, fetchall=True)


def get_doctors_with_location():
    """
    Get all doctors who have clinic location set (for map view)
    """
    query = """
        SELECT u.id, u.full_name, u.email, u.phone,
               d.specialization, d.experience_years, d.consultation_fee,
               d.average_rating, d.total_ratings, d.clinic_address, d.latitude, d.longitude, d.consultation_modes, d.qualification
        FROM users u
        JOIN doctor_details d ON u.id = d.user_id
        WHERE u.role = 'DOCTOR' 
        AND d.latitude IS NOT NULL 
        AND d.longitude IS NOT NULL
        ORDER BY d.average_rating DESC, u.full_name
    """
    return execute_query(query, fetchall=True)


def get_doctor_details(doctor_id):
    """
    Get doctor details by user ID including ratings
    """
    query = """
        SELECT u.*, d.specialization, d.qualification, d.experience_years, 
               d.consultation_fee, d.schedule_json, d.average_rating, d.total_ratings
        FROM users u
        JOIN doctor_details d ON u.id = d.user_id
        WHERE u.id = ?
    """
    return execute_query(query, (doctor_id,), fetchone=True)


def get_patient_details(patient_id):
    """
    Get patient details by user ID
    """
    query = """
        SELECT u.*, p.blood_group, p.allergies, p.chronic_conditions, p.emergency_contact
        FROM users u
        LEFT JOIN patient_details p ON u.id = p.user_id
        WHERE u.id = ?
    """
    return execute_query(query, (patient_id,), fetchone=True)


def update_user_basic_info(user_id, full_name, phone, gender, dob):
    """
    Update basic user information
    """
    query = """
        UPDATE users 
        SET full_name = ?, phone = ?, gender = ?, dob = ?
        WHERE id = ?
    """
    return execute_query(query, (full_name, phone, gender, dob, user_id), commit=True)


def update_patient_details(user_id, blood_group, allergies, chronic_conditions, emergency_contact):
    """
    Update patient-specific details
    """
    query = """
        UPDATE patient_details 
        SET blood_group = ?, allergies = ?, chronic_conditions = ?, emergency_contact = ?
        WHERE user_id = ?
    """
    return execute_query(query, (blood_group, allergies, chronic_conditions, emergency_contact, user_id), commit=True)


def update_doctor_details(user_id, specialization, qualification, experience_years, consultation_fee):
    """
    Update doctor-specific details
    """
    query = """
        UPDATE doctor_details 
        SET specialization = ?, qualification = ?, experience_years = ?, consultation_fee = ?
        WHERE user_id = ?
    """
    return execute_query(query, (specialization, qualification, experience_years, consultation_fee, user_id), commit=True)


# ==================== APPOINTMENT FUNCTIONS ====================

def create_appointment(patient_id, doctor_id, date, time, symptoms=None, consultation_mode='PHYSICAL'):
    """
    Create a new appointment and notify the doctor
    """
    # Generate Meet link if consultation mode is ONLINE
    meet_link = None
    if consultation_mode == 'ONLINE':
        meet_link = generate_meet_link()
    
    query = """
        INSERT INTO appointments (patient_id, doctor_id, date, time, symptoms, status, consultation_mode, meet_link)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """
    appointment_id = execute_query(query, (patient_id, doctor_id, date, time, symptoms, consultation_mode, meet_link), commit=True)
    
    # Get patient name for notification
    patient_query = "SELECT full_name FROM users WHERE id = ?"
    patient = execute_query(patient_query, (patient_id,), fetchone=True)
    
    if appointment_id and patient:
        # Create notification for doctor
        mode_text = "Online" if consultation_mode == 'ONLINE' else "Physical"
        message = f"{patient['full_name']} has requested a {mode_text} appointment for {date} at {time}"
        create_notification(
            user_id=doctor_id,
            notification_type='APPOINTMENT_REQUESTED',
            message=message,
            link='/doctor/appointments',
            appointment_id=appointment_id
        )
    
    return appointment_id


def get_patient_appointments(patient_id):
    """
    Get all appointments for a patient with doctor details
    """
    query = """
        SELECT a.*, 
               u.full_name as doctor_name, 
               d.specialization, 
               d.consultation_fee,
               d.clinic_address
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        WHERE a.patient_id = ?
        ORDER BY a.date DESC, a.time DESC
    """
    return execute_query(query, (patient_id,), fetchall=True)


def get_doctor_appointments(doctor_id):
    """
    Get all appointments for a doctor with patient details
    Ordered by newest requests first (by created_at)
    """
    query = """
        SELECT a.*, 
               u.full_name as patient_name, 
               u.phone as patient_phone,
               u.gender as patient_gender,
               u.dob as patient_dob
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ?
        ORDER BY a.created_at DESC
    """
    return execute_query(query, (doctor_id,), fetchall=True)


def get_doctor_patients(doctor_id):
    """
    Get all unique patients who have had appointments with this doctor
    Returns patient details along with appointment count and last visit
    """
    query = """
        SELECT DISTINCT
               u.id,
               u.full_name,
               u.email,
               u.phone,
               u.gender,
               u.dob,
               p.blood_group,
               p.allergies,
               p.chronic_conditions,
               p.emergency_contact,
               COUNT(DISTINCT a.id) as total_appointments,
               MAX(a.date) as last_visit,
               SUM(CASE WHEN a.status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_appointments
        FROM users u
        JOIN patient_details p ON u.id = p.user_id
        JOIN appointments a ON u.id = a.patient_id
        WHERE a.doctor_id = ? AND a.status IN ('CONFIRMED', 'COMPLETED')
        GROUP BY u.id, u.full_name, u.email, u.phone, u.gender, u.dob, 
                 p.blood_group, p.allergies, p.chronic_conditions, p.emergency_contact
        ORDER BY MAX(a.date) DESC
    """
    return execute_query(query, (doctor_id,), fetchall=True)


def get_appointment_by_id(appointment_id):
    """
    Get a specific appointment by ID
    """
    query = """
        SELECT a.*,
               p.full_name as patient_name,
               d.full_name as doctor_name,
               dd.specialization
        FROM appointments a
        JOIN users p ON a.patient_id = p.id
        JOIN users d ON a.doctor_id = d.id
        JOIN doctor_details dd ON d.id = dd.user_id
        WHERE a.id = ?
    """
    return execute_query(query, (appointment_id,), fetchone=True)


def get_doctor_stats(doctor_id):
    """
    Get statistics for doctor dashboard
    Returns: pending appointments, today's appointments, total patients, this month stats
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    
    # Get current month and year
    current_month = get_ist_today().strftime('%Y-%m')
    
    # Get pending appointments count
    pending_query = """
        SELECT COUNT(*) as count
        FROM appointments
        WHERE doctor_id = ? AND status = 'PENDING'
    """
    pending_result = execute_query(pending_query, (doctor_id,), fetchone=True)
    pending_count = pending_result['count'] if pending_result else 0
    
    # Get today's appointments count (CONFIRMED or COMPLETED)
    today_query = """
        SELECT COUNT(*) as count
        FROM appointments
        WHERE doctor_id = ? AND date = ? AND status IN ('CONFIRMED', 'COMPLETED')
    """
    today_result = execute_query(today_query, (doctor_id, today), fetchone=True)
    today_count = today_result['count'] if today_result else 0
    
    # Get total unique patients count
    patients_query = """
        SELECT COUNT(DISTINCT patient_id) as count
        FROM appointments
        WHERE doctor_id = ? AND status IN ('CONFIRMED', 'COMPLETED')
    """
    patients_result = execute_query(patients_query, (doctor_id,), fetchone=True)
    patients_count = patients_result['count'] if patients_result else 0
    
    # Get this month's appointments count
    month_appointments_query = """
        SELECT COUNT(*) as count
        FROM appointments
        WHERE doctor_id = ? AND strftime('%Y-%m', date) = ? AND status IN ('CONFIRMED', 'COMPLETED')
    """
    month_appt_result = execute_query(month_appointments_query, (doctor_id, current_month), fetchone=True)
    month_appointments = month_appt_result['count'] if month_appt_result else 0
    
    # Get this month's revenue
    month_revenue_query = """
        SELECT SUM(dd.consultation_fee) as revenue
        FROM appointments a
        JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.doctor_id = ? AND strftime('%Y-%m', a.date) = ? AND a.status IN ('CONFIRMED', 'COMPLETED')
    """
    month_revenue_result = execute_query(month_revenue_query, (doctor_id, current_month), fetchone=True)
    month_revenue = month_revenue_result['revenue'] if month_revenue_result and month_revenue_result['revenue'] else 0
    
    # Get average rating
    rating_query = """
        SELECT average_rating, total_ratings
        FROM doctor_details
        WHERE user_id = ?
    """
    rating_result = execute_query(rating_query, (doctor_id,), fetchone=True)
    avg_rating = rating_result['average_rating'] if rating_result else 0
    total_ratings = rating_result['total_ratings'] if rating_result else 0
    
    return {
        'pending_appointments': pending_count,
        'today_appointments': today_count,
        'total_patients': patients_count,
        'month_appointments': month_appointments,
        'month_revenue': month_revenue,
        'average_rating': avg_rating,
        'total_ratings': total_ratings
    }


def get_doctor_today_appointments(doctor_id):
    """
    Get today's appointments for doctor dashboard widget
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    
    query = """
        SELECT a.*, 
               u.full_name as patient_name,
               u.phone as patient_phone
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ? AND a.date = ? AND a.status IN ('CONFIRMED', 'COMPLETED')
        ORDER BY a.time ASC
    """
    return execute_query(query, (doctor_id, today), fetchall=True)


def update_appointment_status(appointment_id, status):
    """
    Update appointment status (PENDING, CONFIRMED, REJECTED, COMPLETED)
    """
    query = """
        UPDATE appointments
        SET status = ?
        WHERE id = ?
    """
    return execute_query(query, (status, appointment_id), commit=True)


def cancel_appointment(appointment_id):
    """
    Delete/cancel an appointment
    """
    query = "DELETE FROM appointments WHERE id = ?"
    return execute_query(query, (appointment_id,), commit=True)


def mark_follow_up_required(appointment_id, follow_up_date, doctor_id, patient_id):
    """
    Mark appointment as requiring follow-up and create notification
    """
    # Update appointment with follow-up details
    query = """
        UPDATE appointments
        SET follow_up_required = 1, follow_up_date = ?
        WHERE id = ?
    """
    execute_query(query, (follow_up_date, appointment_id), commit=True)
    
    # Create notification for patient
    message = f"Your doctor recommends a follow-up visit on {follow_up_date}"
    create_notification(
        user_id=patient_id,
        notification_type='FOLLOW_UP_REQUIRED',
        message=message,
        link='/patient/appointments',
        appointment_id=appointment_id
    )
    
    return True


def create_follow_up_appointment(parent_appointment_id, patient_id, doctor_id, date, time):
    """
    Create a follow-up appointment linked to parent appointment
    """
    query = """
        INSERT INTO appointments (patient_id, doctor_id, date, time, status, parent_appointment_id)
        VALUES (?, ?, ?, ?, 'PENDING', ?)
    """
    return execute_query(query, (patient_id, doctor_id, date, time, parent_appointment_id), commit=True)


def get_follow_up_recommendations(patient_id):
    """
    Get appointments that require follow-up but haven't been scheduled yet
    """
    query = """
        SELECT 
            a.id, a.date as original_date, a.follow_up_date,
            u.full_name as doctor_name,
            dd.specialization
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.patient_id = ? 
        AND a.follow_up_required = 1
        AND a.status = 'COMPLETED'
        AND NOT EXISTS (
            SELECT 1 FROM appointments f 
            WHERE f.parent_appointment_id = a.id
        )
        ORDER BY a.follow_up_date ASC
    """
    return execute_query(query, (patient_id,), fetchall=True)


def get_patient_follow_ups(patient_id):
    """
    Get all follow-up appointments for a patient (both pending and completed)
    """
    query = """
        SELECT 
            a.id,
            a.date as appointment_date,
            a.time as appointment_time,
            a.follow_up_date,
            a.status,
            a.symptoms,
            a.parent_appointment_id,
            a.consultation_mode,
            a.meet_link,
            u.full_name as doctor_name,
            dd.specialization,
            dd.consultation_fee,
            dd.clinic_address
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.patient_id = ?
        AND a.follow_up_required = 1
        AND a.status = 'COMPLETED'
        ORDER BY a.date DESC
    """
    return execute_query(query, (patient_id,), fetchall=True)


def mark_follow_up_complete(appointment_id):
    """
    Mark a follow-up appointment as complete (remove follow-up requirement)
    """
    query = """
        UPDATE appointments
        SET follow_up_required = 0
        WHERE id = ?
    """
    return execute_query(query, (appointment_id,), commit=True)


# ==================== PRESCRIPTION FUNCTIONS ====================

def create_prescription(doctor_id, patient_id, appointment_id, diagnosis, medicines_json, notes=None):
    """
    Create a new prescription
    """
    query = """
        INSERT INTO prescriptions (doctor_id, patient_id, appointment_id, diagnosis, medicines_json, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (doctor_id, patient_id, appointment_id, diagnosis, medicines_json, notes), commit=True)


def get_patient_prescriptions(patient_id):
    """
    Get all prescriptions for a patient
    """
    query = """
        SELECT p.*, 
               u.full_name as doctor_name,
               d.specialization
        FROM prescriptions p
        JOIN users u ON p.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        WHERE p.patient_id = ?
        ORDER BY p.created_at DESC
    """
    return execute_query(query, (patient_id,), fetchall=True)


def get_doctor_prescriptions(doctor_id):
    """
    Get all prescriptions written by a doctor
    """
    query = """
        SELECT p.*, 
               u.full_name as patient_name
        FROM prescriptions p
        JOIN users u ON p.patient_id = u.id
        WHERE p.doctor_id = ?
        ORDER BY p.created_at DESC
    """
    return execute_query(query, (doctor_id,), fetchall=True)


def get_prescription_by_id(prescription_id):
    """
    Get a specific prescription by ID
    """
    query = """
        SELECT p.*,
               doc.full_name as doctor_name,
               dd.specialization,
               pat.full_name as patient_name
        FROM prescriptions p
        JOIN users doc ON p.doctor_id = doc.id
        JOIN doctor_details dd ON doc.id = dd.user_id
        JOIN users pat ON p.patient_id = pat.id
        WHERE p.id = ?
    """
    return execute_query(query, (prescription_id,), fetchone=True)


# ==================== UPLOADED PRESCRIPTION FUNCTIONS ====================

def create_uploaded_prescription(patient_id, filename, extracted_data, explanation=None):
    """
    Create a new uploaded prescription record
    extracted_data should be JSON string
    """
    query = """
        INSERT INTO uploads (patient_id, filename, extracted_data, explanation, upload_type)
        VALUES (?, ?, ?, ?, 'PRESCRIPTION')
    """
    return execute_query(query, (patient_id, filename, extracted_data, explanation), commit=True)


def get_patient_uploaded_prescriptions(patient_id):
    """
    Get all uploaded prescriptions for a patient
    """
    query = """
        SELECT *
        FROM uploads
        WHERE patient_id = ? AND upload_type = 'PRESCRIPTION'
        ORDER BY uploaded_at DESC
    """
    return execute_query(query, (patient_id,), fetchall=True)


def delete_uploaded_prescription(upload_id):
    """
    Delete an uploaded prescription
    """
    query = "DELETE FROM uploads WHERE id = ?"
    return execute_query(query, (upload_id,), commit=True)


# --------------------------------------------------
# 📬 Notification Functions
# --------------------------------------------------

def create_notification(user_id, notification_type, message, link=None, appointment_id=None, prescription_id=None):
    """
    Create a notification for a user
    
    Args:
        user_id: ID of the user to notify
        notification_type: Type of notification (APPOINTMENT_ACCEPTED, APPOINTMENT_REJECTED, PRESCRIPTION_WRITTEN)
        message: Notification message text
        link: URL to navigate when clicked (optional for rejected appointments)
        appointment_id: Related appointment ID (optional)
        prescription_id: Related prescription ID (optional)
    
    Returns:
        Notification ID if successful, None otherwise
    """
    query = """
        INSERT INTO notifications (user_id, type, message, link, appointment_id, prescription_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (user_id, notification_type, message, link, appointment_id, prescription_id), commit=True)


def get_user_notifications(user_id, unread_only=False):
    """
    Get all notifications for a user (with automatic cleanup of old read notifications)
    
    Args:
        user_id: ID of the user
        unread_only: If True, only return unread notifications
    
    Returns:
        List of notification dictionaries
    """
    # Clean up old read notifications (older than 7 days)
    cleanup_query = """
        DELETE FROM notifications
        WHERE user_id = ? AND is_read = 1 
        AND datetime(created_at) < datetime('now', '-7 days')
    """
    execute_query(cleanup_query, (user_id,), commit=True)
    
    if unread_only:
        query = """
            SELECT * FROM notifications
            WHERE user_id = ? AND is_read = 0
            ORDER BY created_at DESC
            LIMIT 50
        """
    else:
        query = """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """
    return execute_query(query, (user_id,), fetchall=True)


def get_unread_notification_count(user_id):
    """
    Get count of unread notifications for a user
    
    Args:
        user_id: ID of the user
    
    Returns:
        Count of unread notifications
    """
    query = """
        SELECT COUNT(*) as count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """
    result = execute_query(query, (user_id,), fetchone=True)
    return result['count'] if result else 0


def mark_notifications_as_read(user_id):
    """
    Mark all unread notifications as read for a user
    
    Args:
        user_id: ID of the user
    
    Returns:
        True if successful
    """
    query = """
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ? AND is_read = 0
    """
    execute_query(query, (user_id,), commit=True)
    return True


def delete_read_notifications(user_id):
    """
    Delete all read notifications for a user immediately (instant cleanup)
    This is called when user opens notification dropdown
    
    Args:
        user_id: ID of the user
    
    Returns:
        True if successful
    """
    query = """
        DELETE FROM notifications
        WHERE user_id = ? AND is_read = 1
    """
    execute_query(query, (user_id,), commit=True)
    return True


def cleanup_old_notifications():
    """
    Global cleanup function - delete all notifications older than 30 days
    Can be called periodically or on app startup
    
    Returns:
        Number of deleted notifications
    """
    query = """
        DELETE FROM notifications
        WHERE datetime(created_at) < datetime('now', '-30 days')
    """
    execute_query(query, (), commit=True)
    return True


# ========================================
# 🌟 DOCTOR RATING FUNCTIONS
# ========================================

def create_rating(doctor_id, patient_id, appointment_id, rating, review_text=None):
    """
    Create a new rating for a doctor
    
    Args:
        doctor_id: ID of the doctor being rated
        patient_id: ID of the patient giving the rating
        appointment_id: ID of the completed appointment
        rating: Rating value (1-5)
        review_text: Optional review text
    
    Returns:
        Rating ID
    """
    query = """
        INSERT INTO doctor_ratings (doctor_id, patient_id, appointment_id, rating, review_text)
        VALUES (?, ?, ?, ?, ?)
    """
    rating_id = execute_query(query, (doctor_id, patient_id, appointment_id, rating, review_text), commit=True)
    
    # Update doctor's average rating
    update_doctor_average_rating(doctor_id)
    
    return rating_id


def update_doctor_average_rating(doctor_id):
    """
    Recalculate and update doctor's average rating
    
    Args:
        doctor_id: ID of the doctor
    """
    # Calculate average
    query = """
        SELECT AVG(rating) as avg_rating, COUNT(*) as total_ratings
        FROM doctor_ratings
        WHERE doctor_id = ?
    """
    result = execute_query(query, (doctor_id,), fetchone=True)
    
    avg_rating = result['avg_rating'] if result['avg_rating'] else 0.0
    total_ratings = result['total_ratings'] if result['total_ratings'] else 0
    
    # Update doctor_details
    update_query = """
        UPDATE doctor_details
        SET average_rating = ?, total_ratings = ?
        WHERE user_id = ?
    """
    execute_query(update_query, (avg_rating, total_ratings, doctor_id), commit=True)


def get_doctor_ratings(doctor_id, limit=10):
    """
    Get all ratings for a doctor with patient info
    
    Args:
        doctor_id: ID of the doctor
        limit: Maximum number of ratings to return
    
    Returns:
        List of rating dictionaries
    """
    query = """
        SELECT 
            dr.id,
            dr.rating,
            dr.review_text,
            dr.created_at,
            u.full_name as patient_name
        FROM doctor_ratings dr
        JOIN users u ON dr.patient_id = u.id
        WHERE dr.doctor_id = ?
        ORDER BY dr.created_at DESC
        LIMIT ?
    """
    return execute_query(query, (doctor_id, limit), fetchall=True)


def check_existing_rating(patient_id, appointment_id):
    """
    Check if patient already rated this appointment
    
    Args:
        patient_id: ID of the patient
        appointment_id: ID of the appointment
    
    Returns:
        Rating dict if exists, None otherwise
    """
    query = """
        SELECT * FROM doctor_ratings
        WHERE patient_id = ? AND appointment_id = ?
    """
    return execute_query(query, (patient_id, appointment_id), fetchone=True)


def get_doctor_average_rating(doctor_id):
    """
    Get doctor's average rating and total count
    
    Args:
        doctor_id: ID of the doctor
    
    Returns:
        Dict with average_rating and total_ratings
    """
    query = """
        SELECT average_rating, total_ratings
        FROM doctor_details
        WHERE user_id = ?
    """
    result = execute_query(query, (doctor_id,), fetchone=True)
    
    if result:
        return {
            'average_rating': result['average_rating'] or 0.0,
            'total_ratings': result['total_ratings'] or 0
        }
    return {'average_rating': 0.0, 'total_ratings': 0}


# ============================================================================
# SEARCH FUNCTIONS
# ============================================================================

def search_doctors(query):
    """
    Search doctors by name, specialization, or qualification
    Returns list of doctors matching the search query
    """
    search_pattern = f"%{query}%"
    sql = """
        SELECT u.*, d.specialization, d.qualification, d.experience_years, d.consultation_fee,
               d.average_rating, d.total_ratings
        FROM users u
        JOIN doctor_details d ON u.id = d.user_id
        WHERE u.role = 'DOCTOR'
        AND (
            u.full_name LIKE ? COLLATE NOCASE
            OR d.specialization LIKE ? COLLATE NOCASE
            OR d.qualification LIKE ? COLLATE NOCASE
        )
        ORDER BY d.average_rating DESC, u.full_name
        LIMIT 20
    """
    return execute_query(sql, (search_pattern, search_pattern, search_pattern), fetchall=True)


def search_patients(query, doctor_id=None):
    """
    Search patients by name, email, or phone
    Optionally filter by doctor's patients only
    """
    search_pattern = f"%{query}%"
    
    if doctor_id:
        # Search only patients who have appointments with this doctor
        sql = """
            SELECT DISTINCT u.*, p.blood_group
            FROM users u
            LEFT JOIN patient_details p ON u.id = p.user_id
            INNER JOIN appointments a ON u.id = a.patient_id
            WHERE u.role = 'PATIENT'
            AND a.doctor_id = ?
            AND (
                u.full_name LIKE ? COLLATE NOCASE
                OR u.email LIKE ? COLLATE NOCASE
                OR u.phone LIKE ? COLLATE NOCASE
            )
            ORDER BY u.full_name
            LIMIT 20
        """
        return execute_query(sql, (doctor_id, search_pattern, search_pattern, search_pattern), fetchall=True)
    else:
        # Search all patients (admin functionality)
        sql = """
            SELECT u.*, p.blood_group
            FROM users u
            LEFT JOIN patient_details p ON u.id = p.user_id
            WHERE u.role = 'PATIENT'
            AND (
                u.full_name LIKE ? COLLATE NOCASE
                OR u.email LIKE ? COLLATE NOCASE
                OR u.phone LIKE ? COLLATE NOCASE
            )
            ORDER BY u.full_name
            LIMIT 20
        """
        return execute_query(sql, (search_pattern, search_pattern, search_pattern), fetchall=True)


# ============================================================================
# LAB REPORT FUNCTIONS
# ============================================================================

def create_lab_report(patient_id, test_type, test_date, report_image, extracted_values_json, notes=None):
    """
    Create a new lab report entry
    """
    query = """
        INSERT INTO lab_reports 
        (patient_id, test_type, test_date, report_image, extracted_values_json, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, 
                        (patient_id, test_type, test_date, report_image, extracted_values_json, notes), 
                        commit=True)


def get_patient_lab_reports(patient_id, test_type=None):
    """
    Get all lab reports for a patient, optionally filtered by test type
    Ordered by test_date descending (newest first)
    """
    if test_type:
        query = """
            SELECT * FROM lab_reports
            WHERE patient_id = ? AND test_type = ?
            ORDER BY test_date DESC, uploaded_at DESC
        """
        return execute_query(query, (patient_id, test_type), fetchall=True)
    else:
        query = """
            SELECT * FROM lab_reports
            WHERE patient_id = ?
            ORDER BY test_date DESC, uploaded_at DESC
        """
        return execute_query(query, (patient_id,), fetchall=True)


def get_lab_report_by_id(report_id):
    """
    Get a specific lab report by ID
    """
    query = "SELECT * FROM lab_reports WHERE id = ?"
    return execute_query(query, (report_id,), fetchone=True)


def delete_lab_report(report_id):
    """
    Delete a lab report
    """
    query = "DELETE FROM lab_reports WHERE id = ?"
    return execute_query(query, (report_id,), commit=True)


def get_lab_report_trends(patient_id, test_type, parameter_name, limit=10):
    """
    Get trend data for a specific health parameter over time
    Returns list of {test_date, value} for charting
    """
    query = """
        SELECT test_date, extracted_values_json
        FROM lab_reports
        WHERE patient_id = ? AND test_type = ?
        ORDER BY test_date ASC
        LIMIT ?
    """
    reports = execute_query(query, (patient_id, test_type, limit), fetchall=True)
    
    trends = []
    for report in reports:
        if report['extracted_values_json']:
            import json
            values = json.loads(report['extracted_values_json'])
            if parameter_name in values:
                trends.append({
                    'date': report['test_date'],
                    'value': values[parameter_name]
                })
    
    return trends


def get_patient_history(patient_id):
    """
    Get complete patient history timeline: appointments, prescriptions, and lab reports
    Returns combined data sorted by date
    """
    history = []
    
    # Get appointments
    appointments_query = """
        SELECT 
            a.id, a.date, a.time, a.status, a.symptoms,
            u.full_name as doctor_name,
            dd.specialization, dd.consultation_fee
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.patient_id = ?
        ORDER BY a.date DESC
    """
    appointments = execute_query(appointments_query, (patient_id,), fetchall=True)
    
    for apt in appointments:
        history.append({
            'type': 'appointment',
            'date': apt['date'],
            'time': apt.get('time', ''),
            'title': f"Appointment with Dr. {apt['doctor_name']}",
            'status': apt['status'],
            'details': {
                'specialization': apt['specialization'],
                'symptoms': apt['symptoms'],
                'consultation_fee': apt.get('consultation_fee')
            }
        })
    
    # Get prescriptions
    prescriptions_query = """
        SELECT 
            p.id, p.created_at, p.diagnosis, p.medicines_json,
            u.full_name as doctor_name,
            dd.specialization
        FROM prescriptions p
        JOIN users u ON p.doctor_id = u.id
        LEFT JOIN doctor_details dd ON p.doctor_id = dd.user_id
        WHERE p.patient_id = ?
        ORDER BY p.created_at DESC
    """
    prescriptions = execute_query(prescriptions_query, (patient_id,), fetchall=True)
    
    for presc in prescriptions:
        # Count medicines
        medicine_count = 0
        if presc['medicines_json']:
            try:
                import json
                medicines = json.loads(presc['medicines_json'])
                medicine_count = len(medicines)
            except:
                pass
        
        history.append({
            'type': 'prescription',
            'date': presc['created_at'][:10],
            'time': presc['created_at'][11:16] if len(presc['created_at']) > 10 else '',
            'title': f"Prescription from Dr. {presc['doctor_name']}",
            'status': 'completed',
            'details': {
                'specialization': presc['specialization'],
                'diagnosis': presc['diagnosis'],
                'medicine_count': medicine_count
            }
        })
    
    # Get lab reports
    lab_reports_query = """
        SELECT id, test_type, test_date, notes, extracted_values_json
        FROM lab_reports
        WHERE patient_id = ?
        ORDER BY test_date DESC
    """
    lab_reports = execute_query(lab_reports_query, (patient_id,), fetchall=True)
    
    for report in lab_reports:
        # Get key extracted values
        key_values = {}
        if report['extracted_values_json']:
            try:
                import json
                all_values = json.loads(report['extracted_values_json'])
                # Get first 3 values for display
                key_values = dict(list(all_values.items())[:3])
            except:
                pass
        
        history.append({
            'type': 'lab_report',
            'date': report['test_date'],
            'time': '',
            'title': f"{report['test_type']} Test",
            'status': 'completed',
            'details': {
                'notes': report['notes'],
                'key_values': key_values
            }
        })
    
    # Sort all history by date (most recent first)
    history.sort(key=lambda x: x['date'], reverse=True)
    
    return history


# ==================== VITAL SIGNS ====================

def create_vital_sign(patient_id, vital_type, value, unit, recorded_by=None, notes=None):
    """
    Log a new vital sign reading
    vital_type: 'blood_pressure', 'blood_sugar', 'weight', 'temperature'
    value: string (e.g., "120/80" for BP, "95" for sugar)
    """
    recorded_at = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
    
    query = """
        INSERT INTO vital_signs (patient_id, vital_type, value, unit, recorded_at, recorded_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (patient_id, vital_type, value, unit, recorded_at, recorded_by, notes), commit=True)


def get_patient_vitals(patient_id, vital_type=None, days=30):
    """
    Get patient's vital signs history
    If vital_type is None, returns all vitals
    days: number of days to look back
    """
    from_date = (get_ist_now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    if vital_type:
        query = """
            SELECT vs.*, u.full_name as recorded_by_name
            FROM vital_signs vs
            LEFT JOIN users u ON vs.recorded_by = u.id
            WHERE vs.patient_id = ? AND vs.vital_type = ? AND DATE(vs.recorded_at) >= ?
            ORDER BY vs.recorded_at DESC
        """
        return execute_query(query, (patient_id, vital_type, from_date), fetchall=True)
    else:
        query = """
            SELECT vs.*, u.full_name as recorded_by_name
            FROM vital_signs vs
            LEFT JOIN users u ON vs.recorded_by = u.id
            WHERE vs.patient_id = ? AND DATE(vs.recorded_at) >= ?
            ORDER BY vs.recorded_at DESC
        """
        return execute_query(query, (patient_id, from_date), fetchall=True)


def analyze_vital_trends(patient_id, vital_type):
    """
    Analyze trends for a specific vital type
    Returns: {
        'current': latest value,
        'trend': 'increasing'/'decreasing'/'stable',
        'alert': True/False,
        'alert_message': string
    }
    """
    # Get last 14 days of data
    recent_vitals = get_patient_vitals(patient_id, vital_type, days=14)
    
    if not recent_vitals or len(recent_vitals) < 2:
        return {
            'current': None,
            'trend': 'stable',
            'alert': False,
            'alert_message': None
        }
    
    # Split into recent week and previous week
    mid_point = len(recent_vitals) // 2
    recent_week = recent_vitals[:mid_point] if mid_point > 0 else recent_vitals
    previous_week = recent_vitals[mid_point:] if mid_point > 0 else []
    
    current_value = recent_vitals[0]['value']
    
    # Calculate average for trend (simplified for numeric vitals)
    def extract_numeric(value, vital_type):
        """Extract numeric value from vital reading"""
        if vital_type == 'blood_pressure':
            # Use systolic (first number)
            return float(value.split('/')[0])
        elif vital_type == 'weight':
            return float(value)
        elif vital_type == 'blood_sugar':
            return float(value)
        elif vital_type == 'temperature':
            return float(value)
        return 0
    
    try:
        recent_avg = sum(extract_numeric(v['value'], vital_type) for v in recent_week) / len(recent_week)
        previous_avg = sum(extract_numeric(v['value'], vital_type) for v in previous_week) / len(previous_week) if previous_week else recent_avg
        
        # Determine trend
        diff_percent = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
        
        if diff_percent > 5:
            trend = 'increasing'
        elif diff_percent < -5:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        # Check for alerts based on normal ranges
        alert = False
        alert_message = None
        
        current_numeric = extract_numeric(current_value, vital_type)
        
        if vital_type == 'blood_pressure':
            systolic = current_numeric
            if systolic > 140:
                alert = True
                alert_message = "High blood pressure detected (>140 systolic)"
            elif systolic < 90:
                alert = True
                alert_message = "Low blood pressure detected (<90 systolic)"
        
        elif vital_type == 'blood_sugar':
            if current_numeric > 140:
                alert = True
                alert_message = "High blood sugar detected (>140 mg/dL)"
            elif current_numeric < 70:
                alert = True
                alert_message = "Low blood sugar detected (<70 mg/dL)"
        
        elif vital_type == 'temperature':
            if current_numeric > 99.5:
                alert = True
                alert_message = "Fever detected (>99.5°F)"
            elif current_numeric < 97:
                alert = True
                alert_message = "Low temperature detected (<97°F)"
        
        elif vital_type == 'weight':
            # Check for rapid weight change (>5% in 2 weeks)
            if abs(diff_percent) > 5:
                alert = True
                direction = "gain" if diff_percent > 0 else "loss"
                alert_message = f"Rapid weight {direction} detected ({abs(diff_percent):.1f}%)"
        
        return {
            'current': current_value,
            'trend': trend,
            'alert': alert,
            'alert_message': alert_message,
            'recent_avg': round(recent_avg, 1),
            'previous_avg': round(previous_avg, 1)
        }
    
    except Exception as e:
        return {
            'current': current_value,
            'trend': 'stable',
            'alert': False,
            'alert_message': None
        }


def get_patient_recent_vitals(patient_id):
    """
    Get patient's most recent vitals WITH TREND ANALYSIS for chatbot context.
    Includes current value, 7-day averages, trend direction, percentage change, and alerts.
    Returns formatted string with comprehensive vitals data.
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    yesterday = (get_ist_now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    vital_types = ['blood_pressure', 'blood_sugar', 'weight', 'temperature']
    vitals_summary = []
    
    for vital_type in vital_types:
        # Try today first
        query = """
            SELECT value, unit, recorded_at
            FROM vital_signs
            WHERE patient_id = ? AND vital_type = ? AND DATE(recorded_at) = ?
            ORDER BY recorded_at DESC
            LIMIT 1
        """
        result = execute_query(query, (patient_id, vital_type, today), fetchone=True)
        
        # If not today, try yesterday
        if not result:
            result = execute_query(query, (patient_id, vital_type, yesterday), fetchone=True)
        
        # If still not found, get the last available entry
        if not result:
            query_last = """
                SELECT value, unit, recorded_at
                FROM vital_signs
                WHERE patient_id = ? AND vital_type = ?
                ORDER BY recorded_at DESC
                LIMIT 1
            """
            result = execute_query(query_last, (patient_id, vital_type), fetchone=True)
        
        # Format the vital sign WITH TREND ANALYSIS
        if result:
            value = result['value']
            unit = result['unit']
            recorded_date = result['recorded_at'][:10]
            
            # Determine when it was recorded
            if recorded_date == today:
                when = "today"
            elif recorded_date == yesterday:
                when = "yesterday"
            else:
                when = f"on {recorded_date}"
            
            # Get trend analysis
            trend_data = analyze_vital_trends(patient_id, vital_type)
            
            # Format display name
            vital_names = {
                'blood_pressure': 'Blood Pressure',
                'blood_sugar': 'Blood Sugar',
                'weight': 'Weight',
                'temperature': 'Temperature'
            }
            
            # Build comprehensive vital summary
            vital_line = f"{vital_names[vital_type]}: {value} {unit} ({when})"
            
            # Add trend analysis if available
            if trend_data and trend_data.get('recent_avg'):
                recent_avg = trend_data['recent_avg']
                previous_avg = trend_data.get('previous_avg', 'N/A')
                trend = trend_data['trend']
                
                # Calculate percentage change
                if previous_avg != 'N/A' and previous_avg and recent_avg:
                    try:
                        if vital_type == 'blood_pressure':
                            # For BP, use systolic for percentage
                            recent_sys = float(str(recent_avg).split('/')[0]) if '/' in str(recent_avg) else float(recent_avg)
                            prev_sys = float(str(previous_avg).split('/')[0]) if '/' in str(previous_avg) else float(previous_avg)
                            pct_change = ((recent_sys - prev_sys) / prev_sys) * 100
                        else:
                            pct_change = ((float(recent_avg) - float(previous_avg)) / float(previous_avg)) * 100
                        
                        trend_symbol = "↑" if trend == "increasing" else "↓" if trend == "decreasing" else "→"
                        vital_line += f" | 7-day avg: {recent_avg} {unit}, Trend: {trend.capitalize()} {trend_symbol} {abs(pct_change):.1f}%"
                    except:
                        vital_line += f" | 7-day avg: {recent_avg} {unit}, Trend: {trend.capitalize()}"
                else:
                    vital_line += f" | 7-day avg: {recent_avg} {unit}, Trend: {trend.capitalize()}"
                
                # Add alert if present
                if trend_data.get('alert') and trend_data.get('alert_message'):
                    vital_line += f" | ⚠️ ALERT: {trend_data['alert_message']}"
            
            vitals_summary.append(vital_line)
    
    if vitals_summary:
        return "Patient's Recent Vitals:\n" + "\n".join(vitals_summary)
    else:
        return "No vital signs recorded yet."


def get_patient_medical_summary(patient_id):
    """
    Get compact medical summary for chatbot context (appointments + prescriptions).
    Includes: last appointment, next appointment, active prescriptions count, past visits count.
    Returns formatted string with essential medical history.
    """
    summary_parts = []
    
    # Get last completed appointment
    last_appt_query = """
        SELECT a.date, a.time,
               u.full_name as doctor_name,
               d.specialization,
               p.id as prescription_id,
               p.diagnosis,
               p.medicines_json
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        LEFT JOIN prescriptions p ON a.id = p.appointment_id
        WHERE a.patient_id = ? AND a.status = 'COMPLETED'
        ORDER BY a.date DESC, a.time DESC
        LIMIT 1
    """
    last_appt = execute_query(last_appt_query, (patient_id,), fetchone=True)
    
    if last_appt:
        doctor_info = f"Dr. {last_appt['doctor_name']} ({last_appt['specialization']})"
        appt_date = last_appt['date']
        
        last_appt_text = f"Last Appointment: {doctor_info} on {appt_date}"
        
        if last_appt['prescription_id'] and last_appt['medicines_json']:
            import json
            try:
                meds = json.loads(last_appt['medicines_json'])
                if meds:
                    med_count = len(meds)
                    first_med = meds[0]
                    med_name = first_med.get('name', 'Unknown')
                    dosage = first_med.get('dosage', '')
                    timing = first_med.get('timing', '')
                    
                    if med_count == 1:
                        last_appt_text += f"\n  Prescribed: {med_name} {dosage} ({timing})"
                    else:
                        last_appt_text += f"\n  Prescribed: {med_name} {dosage} ({timing}) + {med_count - 1} more"
            except:
                pass
        
        summary_parts.append(last_appt_text)
    
    # Get next upcoming appointment
    next_appt_query = """
        SELECT a.date, a.time, a.symptoms, a.status,
               u.full_name as doctor_name,
               d.specialization
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        WHERE a.patient_id = ? AND a.status IN ('PENDING', 'CONFIRMED')
        AND a.date >= ?
        ORDER BY a.date ASC, a.time ASC
        LIMIT 1
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    next_appt = execute_query(next_appt_query, (patient_id, today), fetchone=True)
    
    if next_appt:
        doctor_info = f"Dr. {next_appt['doctor_name']} ({next_appt['specialization']})"
        appt_date = next_appt['date']
        appt_time = next_appt['time']
        reason = next_appt['symptoms'] or "Checkup"
        status = next_appt['status']
        
        next_appt_text = f"Next Appointment: {doctor_info} on {appt_date} at {appt_time} (Status: {status})\n  Reason: {reason}"
        summary_parts.append(next_appt_text)
    
    # Get total prescription count
    prescription_count_query = """
        SELECT COUNT(*) as count
        FROM prescriptions
        WHERE patient_id = ?
    """
    presc_count = execute_query(prescription_count_query, (patient_id,), fetchone=True)
    if presc_count and presc_count['count'] > 0:
        summary_parts.append(f"Total Prescriptions Received: {presc_count['count']}")
    
    # Get appointment statistics
    appointment_stats_query = """
        SELECT 
            COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed_count,
            COUNT(CASE WHEN status IN ('PENDING', 'CONFIRMED') THEN 1 END) as upcoming_count,
            COUNT(*) as total_count
        FROM appointments
        WHERE patient_id = ?
    """
    appt_stats = execute_query(appointment_stats_query, (patient_id,), fetchone=True)
    
    if appt_stats and appt_stats['total_count'] > 0:
        stats_text = f"Appointment History: {appt_stats['completed_count']} completed"
        if appt_stats['upcoming_count'] > 0:
            stats_text += f", {appt_stats['upcoming_count']} upcoming/pending"
        summary_parts.append(stats_text)
    
    if summary_parts:
        return "Medical History Summary:\n" + "\n".join(summary_parts)
    else:
        return "No medical history found."


def get_appointment_full_details(patient_id, appointment_id):
    """
    FUNCTION CALLING: Get complete details of a specific appointment.
    Returns: appointment info, diagnosis, full prescription with all medicines.
    """
    query = """
        SELECT a.*,
               u.full_name as doctor_name,
               d.specialization,
               d.qualification,
               p.diagnosis,
               p.medicines_json,
               p.notes
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        LEFT JOIN prescriptions p ON a.id = p.appointment_id
        WHERE a.patient_id = ? AND a.id = ?
    """
    result = execute_query(query, (patient_id, appointment_id), fetchone=True)
    
    if not result:
        return {"error": "Appointment not found"}
    
    import json
    medicines = []
    if result['medicines_json']:
        try:
            medicines = json.loads(result['medicines_json'])
        except:
            pass
    
    return {
        "appointment_id": result['id'],
        "doctor_name": result['doctor_name'],
        "specialization": result['specialization'],
        "date": result['date'],
        "time": result['time'],
        "symptoms": result['symptoms'],
        "diagnosis": result['diagnosis'],
        "medicines": medicines,
        "notes": result['notes'],
        "status": result['status']
    }


def get_all_patient_prescriptions_detailed(patient_id):
    """
    FUNCTION CALLING: Get ALL prescriptions with complete medication details.
    Returns: list of all prescriptions with medicines breakdown.
    """
    prescriptions = get_patient_prescriptions(patient_id)
    
    if not prescriptions:
        return {"message": "No prescriptions found"}
    
    import json
    detailed_list = []
    
    for presc in prescriptions:
        medicines = []
        if presc['medicines_json']:
            try:
                medicines = json.loads(presc['medicines_json'])
            except:
                pass
        
        detailed_list.append({
            "prescription_id": presc['id'],
            "doctor_name": presc['doctor_name'],
            "specialization": presc['specialization'],
            "date": presc['created_at'][:10],
            "diagnosis": presc['diagnosis'],
            "medicines": medicines,
            "notes": presc['notes']
        })
    
    return {"prescriptions": detailed_list, "total_count": len(detailed_list)}


def get_past_appointments_filtered(patient_id, limit=10, doctor_name=None, date_from=None):
    """
    FUNCTION CALLING: Get past appointments with optional filters.
    Can filter by doctor name and date range.
    """
    query = """
        SELECT a.id, a.date, a.time, a.symptoms,
               u.full_name as doctor_name,
               d.specialization,
               p.id as has_prescription,
               p.diagnosis
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        LEFT JOIN prescriptions p ON a.id = p.appointment_id
        WHERE a.patient_id = ? AND a.status = 'COMPLETED'
    """
    
    params = [patient_id]
    
    if doctor_name:
        query += " AND u.full_name LIKE ?"
        params.append(f"%{doctor_name}%")
    
    if date_from:
        query += " AND a.date >= ?"
        params.append(date_from)
    
    query += " ORDER BY a.date DESC, a.time DESC LIMIT ?"
    params.append(limit)
    
    results = execute_query(query, tuple(params), fetchall=True)
    
    if not results:
        return {"message": "No past appointments found", "appointments": []}
    
    appointments = []
    for appt in results:
        appointments.append({
            "appointment_id": appt['id'],
            "doctor_name": appt['doctor_name'],
            "specialization": appt['specialization'],
            "date": appt['date'],
            "time": appt['time'],
            "symptoms": appt['symptoms'],
            "diagnosis": appt['diagnosis'],
            "has_prescription": bool(appt['has_prescription'])
        })
    
    return {"appointments": appointments, "total_count": len(appointments)}


def get_all_appointments_summary(patient_id):
    """
    FUNCTION CALLING: Get ALL appointments (past, upcoming, confirmed, pending, rejected).
    Returns complete appointment list with status for each.
    """
    query = """
        SELECT a.id, a.date, a.time, a.symptoms, a.status, a.created_at,
               u.full_name as doctor_name,
               d.specialization,
               p.id as has_prescription
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_details d ON u.id = d.user_id
        LEFT JOIN prescriptions p ON a.id = p.appointment_id
        WHERE a.patient_id = ?
        ORDER BY a.date DESC, a.time DESC
    """
    
    results = execute_query(query, (patient_id,), fetchall=True)
    
    if not results:
        return {"message": "No appointments found", "appointments": []}
    
    appointments = []
    for appt in results:
        appointments.append({
            "appointment_id": appt['id'],
            "doctor_name": appt['doctor_name'],
            "specialization": appt['specialization'],
            "scheduled_date": appt['date'],
            "scheduled_time": appt['time'],
            "booked_on": appt['created_at'][:10],
            "status": appt['status'],
            "symptoms": appt['symptoms'],
            "has_prescription": bool(appt['has_prescription'])
        })
    
    return {"appointments": appointments, "total_count": len(appointments)}


def get_comprehensive_patient_details(patient_id):
    """
    Get comprehensive patient details for doctor's modal view
    Includes: basic info, vitals history, ALL prescriptions (from ALL doctors), appointment stats
    """
    try:
        # Get basic patient info
        patient_query = """
            SELECT u.id, u.full_name, u.email, u.phone, u.dob, u.gender,
                   p.blood_group, p.allergies, p.chronic_conditions, p.emergency_contact
            FROM users u
            LEFT JOIN patient_details p ON u.id = p.user_id
            WHERE u.id = ? AND u.role = 'PATIENT'
        """
        
        patient = execute_query(patient_query, (patient_id,), fetchone=True)
        
        if not patient:
            return None
        
        # Get vitals history (last 30 days from most recent vital)
        # Query normalized vital_signs table and pivot data by date
        vitals_query = """
            SELECT 
                DATE(recorded_at) as date,
                MAX(CASE WHEN vital_type = 'blood_pressure' THEN value END) as blood_pressure,
                MAX(CASE WHEN vital_type = 'temperature' THEN value END) as temperature,
                MAX(CASE WHEN vital_type = 'weight' THEN value END) as weight,
                MAX(CASE WHEN vital_type = 'blood_sugar' THEN value END) as blood_sugar
            FROM vital_signs
            WHERE patient_id = ?
            AND DATE(recorded_at) >= (
                SELECT DATE(MAX(recorded_at), '-30 days') 
                FROM vital_signs 
                WHERE patient_id = ?
            )
            GROUP BY DATE(recorded_at)
            ORDER BY date DESC
        """
        
        vitals = execute_query(vitals_query, (patient_id, patient_id), fetchall=True)
        
        # Get ALL prescriptions from ALL doctors
        prescriptions_query = """
            SELECT p.id, p.diagnosis, p.medicines_json, p.notes, p.created_at,
                   u.full_name as doctor_name,
                   dd.specialization
            FROM prescriptions p
            JOIN users u ON p.doctor_id = u.id
            LEFT JOIN doctor_details dd ON u.id = dd.user_id
            WHERE p.patient_id = ?
            ORDER BY p.created_at DESC
        """
        
        prescriptions = execute_query(prescriptions_query, (patient_id,), fetchall=True)
        
        # Get appointment statistics
        stats_query = """
            SELECT 
                COUNT(*) as total_appointments,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_appointments,
                MAX(CASE WHEN status = 'COMPLETED' THEN date ELSE NULL END) as last_visit
            FROM appointments
            WHERE patient_id = ?
        """
        
        stats = execute_query(stats_query, (patient_id,), fetchone=True)
    
        # Format the data
        result = {
            'id': patient['id'],
            'full_name': patient['full_name'],
            'email': patient['email'],
            'phone': patient['phone'],
            'dob': patient['dob'],
            'gender': patient['gender'],
            'blood_group': patient['blood_group'],
            'allergies': patient['allergies'],
            'chronic_conditions': patient['chronic_conditions'],
            'emergency_contact': patient['emergency_contact'],
            'total_appointments': stats['total_appointments'] if stats else 0,
            'completed_appointments': stats['completed_appointments'] if stats else 0,
            'last_visit': stats['last_visit'] if stats else None,
            'vitals': [],
            'prescriptions': []
        }
        
        # Format vitals
        if vitals:
            for vital in vitals:
                result['vitals'].append({
                    'date': vital['date'],
                    'blood_pressure': vital['blood_pressure'],
                    'temperature': vital['temperature'],
                    'weight': vital['weight'],
                    'blood_sugar': vital['blood_sugar']
                })
        
        # Format prescriptions with parsed medicines
        if prescriptions:
            for prescription in prescriptions:
                try:
                    medicines = json.loads(prescription['medicines_json']) if prescription['medicines_json'] else []
                except:
                    medicines = []
                
                result['prescriptions'].append({
                    'id': prescription['id'],
                    'date': prescription['created_at'][:10],
                    'diagnosis': prescription['diagnosis'],
                    'notes': prescription['notes'],
                    'doctor_name': prescription['doctor_name'],
                    'specialization': prescription['specialization'],
                    'medicines': medicines
                })
        
        return result
        
    except Exception as e:
        print(f"Error in get_comprehensive_patient_details: {e}")
        import traceback
        traceback.print_exc()
        return None


# Run initialization if executed directly
if __name__ == "__main__":
    init_db()

