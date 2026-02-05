"""
Database Models for MediFriend
Each class represents a table in the SQLite database
"""
from datetime import datetime
import json


class User:
    """
    Stores both Patients & Doctors
    """
    TABLE_NAME = "users"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('PATIENT', 'DOCTOR')),
            phone TEXT,
            gender TEXT,
            dob TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"
        ]


class PatientDetails:
    """
    Additional details specific to patients
    """
    TABLE_NAME = "patient_details"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS patient_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            blood_group TEXT,
            allergies TEXT,
            chronic_conditions TEXT,
            emergency_contact TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_patient_user_id ON patient_details(user_id)"
        ]


class DoctorDetails:
    """
    Additional details specific to doctors
    """
    TABLE_NAME = "doctor_details"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS doctor_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            specialization TEXT NOT NULL,
            qualification TEXT,
            experience_years INTEGER DEFAULT 0,
            consultation_fee REAL DEFAULT 0.0,
            schedule_json TEXT,
            average_rating REAL DEFAULT 0.0,
            total_ratings INTEGER DEFAULT 0,
            clinic_address TEXT,
            latitude REAL,
            longitude REAL,
            consultation_modes TEXT DEFAULT 'PHYSICAL',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_doctor_user_id ON doctor_details(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_doctor_specialization ON doctor_details(specialization)"
        ]


class Appointment:
    """
    Appointment bookings between patients and doctors
    """
    TABLE_NAME = "appointments"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            symptoms TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'COMPLETED')),
            consultation_mode TEXT DEFAULT 'PHYSICAL' CHECK(consultation_mode IN ('PHYSICAL', 'ONLINE')),
            meet_link TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_date TEXT,
            parent_appointment_id INTEGER,
            was_rescheduled INTEGER DEFAULT 0,
            original_date TEXT,
            original_time TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_appointment_patient ON appointments(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_doctor ON appointments(doctor_id)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_date ON appointments(date)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_status ON appointments(status)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_parent ON appointments(parent_appointment_id)"
        ]


class Prescription:
    """
    Formal prescriptions written by doctors
    """
    TABLE_NAME = "prescriptions"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            appointment_id INTEGER,
            diagnosis TEXT,
            medicines_json TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_prescription_patient ON prescriptions(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_prescription_doctor ON prescriptions(doctor_id)",
            "CREATE INDEX IF NOT EXISTS idx_prescription_appointment ON prescriptions(appointment_id)"
        ]


class Upload:
    """
    User uploaded files (prescriptions, lab reports, etc.)
    Stores extracted data as JSON instead of file path
    """
    TABLE_NAME = "uploads"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            extracted_data TEXT,
            explanation TEXT,
            upload_type TEXT DEFAULT 'PRESCRIPTION' CHECK(upload_type IN ('PRESCRIPTION', 'LAB_REPORT', 'OTHER')),
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_upload_patient ON uploads(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_upload_type ON uploads(upload_type)"
        ]


class Notification:
    """
    Notifications for users about appointments, prescriptions, etc.
    """
    TABLE_NAME = "notifications"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('APPOINTMENT_ACCEPTED', 'APPOINTMENT_REJECTED', 'PRESCRIPTION_WRITTEN', 'APPOINTMENT_REQUESTED', 'FOLLOW_UP_REQUIRED')),
            message TEXT NOT NULL,
            link TEXT,
            is_read INTEGER DEFAULT 0,
            appointment_id INTEGER,
            prescription_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_notification_user ON notifications(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_read ON notifications(is_read)",
            "CREATE INDEX IF NOT EXISTS idx_notification_created ON notifications(created_at)"
        ]


class DoctorRating:
    """
    Ratings and reviews for doctors by patients
    """
    TABLE_NAME = "doctor_ratings"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS doctor_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            appointment_id INTEGER,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
            UNIQUE(patient_id, appointment_id)
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_rating_doctor ON doctor_ratings(doctor_id)",
            "CREATE INDEX IF NOT EXISTS idx_rating_patient ON doctor_ratings(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_rating_created ON doctor_ratings(created_at)"
        ]


class LabReport:
    """
    Stores patient lab test reports with AI-extracted values
    """
    TABLE_NAME = "lab_reports"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS lab_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            test_type TEXT NOT NULL,
            test_date TEXT NOT NULL,
            report_image TEXT NOT NULL,
            extracted_values_json TEXT,
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_lab_patient ON lab_reports(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_lab_test_date ON lab_reports(test_date)",
            "CREATE INDEX IF NOT EXISTS idx_lab_test_type ON lab_reports(test_type)"
        ]


class VitalSign:
    """
    Stores patient vital signs over time (BP, sugar, weight, temperature)
    """
    TABLE_NAME = "vital_signs"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS vital_signs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            vital_type TEXT NOT NULL CHECK(vital_type IN ('blood_pressure', 'blood_sugar', 'weight', 'temperature')),
            value TEXT NOT NULL,
            unit TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            recorded_by INTEGER,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_vitals_patient ON vital_signs(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_vitals_type ON vital_signs(vital_type)",
            "CREATE INDEX IF NOT EXISTS idx_vitals_date ON vital_signs(recorded_at)"
        ]


class MedicationReminder:
    """
    Tracks medication reminders for prescriptions
    """
    TABLE_NAME = "medication_reminders"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS medication_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prescription_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            last_sent_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_reminder_patient ON medication_reminders(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_reminder_prescription ON medication_reminders(prescription_id)",
            "CREATE INDEX IF NOT EXISTS idx_reminder_active ON medication_reminders(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_reminder_dates ON medication_reminders(start_date, end_date)"
        ]


class AppointmentSummary:
    """
    AI-generated summaries of appointment discussions
    """
    TABLE_NAME = "appointment_summaries"
    
    @staticmethod
    def create_table_sql():
        return """
        CREATE TABLE IF NOT EXISTS appointment_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            summary_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_summary_appointment ON appointment_summaries(appointment_id)"
        ]


# List of all model classes for easy iteration
ALL_MODELS = [
    User,
    PatientDetails,
    DoctorDetails,
    Appointment,
    Prescription,
    Upload,
    Notification,
    DoctorRating,
    LabReport,
    VitalSign,
    MedicationReminder,
    AppointmentSummary
]
