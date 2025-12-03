"""
Database Connection and Initialization for MediFriend
"""
import sqlite3
import os
from models import ALL_MODELS


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


def insert_doctor_details(user_id, specialization, qualification=None, experience_years=0, consultation_fee=0.0, schedule_json=None):
    """
    Insert doctor-specific details
    """
    query = """
        INSERT INTO doctor_details (user_id, specialization, qualification, experience_years, consultation_fee, schedule_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_query(query, (user_id, specialization, qualification, experience_years, consultation_fee, schedule_json), commit=True)


def get_all_doctors():
    """
    Get all doctors with their details
    """
    query = """
        SELECT u.*, d.specialization, d.experience_years, d.consultation_fee
        FROM users u
        JOIN doctor_details d ON u.id = d.user_id
        WHERE u.role = 'DOCTOR'
        ORDER BY u.full_name
    """
    return execute_query(query, fetchall=True)


def get_doctor_details(doctor_id):
    """
    Get doctor details by user ID
    """
    query = """
        SELECT u.*, d.specialization, d.qualification, d.experience_years, d.consultation_fee, d.schedule_json
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

def create_appointment(patient_id, doctor_id, date, time, symptoms=None):
    """
    Create a new appointment and notify the doctor
    """
    query = """
        INSERT INTO appointments (patient_id, doctor_id, date, time, symptoms, status)
        VALUES (?, ?, ?, ?, ?, 'PENDING')
    """
    appointment_id = execute_query(query, (patient_id, doctor_id, date, time, symptoms), commit=True)
    
    # Get patient name for notification
    patient_query = "SELECT full_name FROM users WHERE id = ?"
    patient = execute_query(patient_query, (patient_id,), fetchone=True)
    
    if appointment_id and patient:
        # Create notification for doctor
        message = f"{patient['full_name']} has requested an appointment for {date} at {time}"
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
               d.consultation_fee
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
    Returns: pending appointments count, today's appointments count, total patients count
    """
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    
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
    
    return {
        'pending_appointments': pending_count,
        'today_appointments': today_count,
        'total_patients': patients_count
    }


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


# Run initialization if executed directly
if __name__ == "__main__":
    init_db()
