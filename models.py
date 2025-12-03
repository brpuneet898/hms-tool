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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    
    @staticmethod
    def create_indexes_sql():
        return [
            "CREATE INDEX IF NOT EXISTS idx_appointment_patient ON appointments(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_doctor ON appointments(doctor_id)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_date ON appointments(date)",
            "CREATE INDEX IF NOT EXISTS idx_appointment_status ON appointments(status)"
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
            type TEXT NOT NULL CHECK(type IN ('APPOINTMENT_ACCEPTED', 'APPOINTMENT_REJECTED', 'PRESCRIPTION_WRITTEN', 'APPOINTMENT_REQUESTED')),
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


# List of all model classes for easy iteration
ALL_MODELS = [
    User,
    PatientDetails,
    DoctorDetails,
    Appointment,
    Prescription,
    Upload,
    Notification
]
