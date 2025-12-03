"""
Authentication Routes for MediFriend
Handles user signup, login, and logout
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    get_user_by_email, 
    insert_user, 
    insert_patient_details,
    insert_doctor_details,
    get_patient_details,
    get_doctor_details,
    update_user_basic_info,
    update_patient_details,
    update_doctor_details
)

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """
    Decorator to require login for routes
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """
    Decorator to require specific role for routes
    """
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('role') != role:
                flash(f'This page is only accessible to {role.lower()}s.', 'danger')
                return redirect(url_for('home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Patient signup page
    """
    if request.method == 'POST':
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        country_code = request.form.get('country_code', '+91').strip()
        phone = request.form.get('phone', '').strip()
        # Combine country code with phone number
        if phone:
            phone = f"{country_code} {phone}"
        gender = request.form.get('gender', '').strip()
        dob = request.form.get('dob', '').strip()
        
        # Optional patient details
        blood_group = request.form.get('blood_group', '').strip()
        allergies = request.form.get('allergies', '').strip()
        chronic_conditions = request.form.get('chronic_conditions', '').strip()
        emergency_country_code = request.form.get('emergency_country_code', '+91').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()
        # Combine country code with emergency contact
        if emergency_contact:
            emergency_contact = f"{emergency_country_code} {emergency_contact}"
        
        # Validation
        if not full_name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('signup.html')
        
        # Check if email already exists
        existing_user = get_user_by_email(email)
        if existing_user:
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            # Hash password
            password_hash = generate_password_hash(password)
            
            # Insert user
            user_id = insert_user(
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role='PATIENT',
                phone=phone,
                gender=gender,
                dob=dob
            )
            
            # Insert patient details
            insert_patient_details(
                user_id=user_id,
                blood_group=blood_group,
                allergies=allergies,
                chronic_conditions=chronic_conditions,
                emergency_contact=emergency_contact
            )
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'danger')
            return render_template('signup.html')
    
    return render_template('signup.html')


@auth_bp.route('/doctor-signup', methods=['GET', 'POST'])
def doctor_signup():
    """
    Doctor signup page
    """
    if request.method == 'POST':
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        country_code = request.form.get('country_code', '+91').strip()
        phone = request.form.get('phone', '').strip()
        # Combine country code with phone number
        if phone:
            phone = f"{country_code} {phone}"
        gender = request.form.get('gender', '').strip()
        dob = request.form.get('dob', '').strip()
        
        # Doctor-specific details
        specialization = request.form.get('specialization', '').strip()
        experience_years = request.form.get('experience_years', '').strip()
        consultation_fee = request.form.get('consultation_fee', '').strip()
        qualification = request.form.get('qualification', '').strip()
        
        # Validation
        if not full_name or not email or not password or not specialization:
            flash('Please fill in all required fields.', 'danger')
            return render_template('doctor_signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('doctor_signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('doctor_signup.html')
        
        # Check if email already exists
        existing_user = get_user_by_email(email)
        if existing_user:
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            # Hash password
            password_hash = generate_password_hash(password)
            
            # Insert user
            user_id = insert_user(
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role='DOCTOR',
                phone=phone,
                gender=gender,
                dob=dob
            )
            
            if not user_id:
                flash('Error creating user account.', 'danger')
                return render_template('doctor_signup.html')
            
            # Insert doctor details
            try:
                insert_doctor_details(
                    user_id=user_id,
                    specialization=specialization,
                    qualification=qualification,
                    experience_years=int(experience_years) if experience_years else 0,
                    consultation_fee=float(consultation_fee) if consultation_fee else 0.0
                )
            except Exception as doctor_error:
                print(f"Error inserting doctor details: {doctor_error}")
                flash(f'Account created but error saving doctor details: {str(doctor_error)}', 'warning')
                return redirect(url_for('auth.login'))
            
            flash('Doctor account created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            print(f"Error in doctor signup: {e}")
            flash(f'Error creating account: {str(e)}', 'danger')
            return render_template('doctor_signup.html')
    
    return render_template('doctor_signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page for both patients and doctors
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
        
        # Get user from database
        user = get_user_by_email(email)
        
        if not user:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        
        # Check password
        if not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        
        # Set session
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['full_name'] = user['full_name']
        session['role'] = user['role']
        
        flash(f'Welcome back, {user["full_name"]}!', 'success')
        
        # Redirect based on role
        if user['role'] == 'DOCTOR':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """
    Logout user and clear session
    """
    user_name = session.get('full_name', 'User')
    session.clear()
    flash(f'Goodbye, {user_name}! You have been logged out.', 'info')
    return redirect(url_for('home'))


@auth_bp.route('/profile')
@login_required
def profile():
    """
    User profile page (works for both patients and doctors)
    """
    user_id = session.get('user_id')
    role = session.get('role')
    
    if role == 'PATIENT':
        user_data = get_patient_details(user_id)
    else:
        user_data = get_doctor_details(user_id)
    
    return render_template('profile.html', user=user_data, role=role)


@auth_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Edit user profile
    """
    user_id = session.get('user_id')
    role = session.get('role')
    
    if request.method == 'POST':
        try:
            # Get basic info
            full_name = request.form.get('full_name', '').strip()
            phone = request.form.get('phone', '').strip()
            gender = request.form.get('gender', '').strip()
            dob = request.form.get('dob', '').strip()
            
            # Update basic user info
            update_user_basic_info(user_id, full_name, phone, gender, dob)
            
            # Update role-specific details
            if role == 'PATIENT':
                blood_group = request.form.get('blood_group', '').strip()
                allergies = request.form.get('allergies', '').strip()
                chronic_conditions = request.form.get('chronic_conditions', '').strip()
                emergency_contact = request.form.get('emergency_contact', '').strip()
                
                update_patient_details(user_id, blood_group or None, allergies or None, 
                                     chronic_conditions or None, emergency_contact or None)
            
            elif role == 'DOCTOR':
                specialization = request.form.get('specialization', '').strip()
                qualification = request.form.get('qualification', '').strip()
                experience_years = request.form.get('experience_years', 0)
                consultation_fee = request.form.get('consultation_fee', 0.0)
                
                update_doctor_details(user_id, specialization, qualification or None,
                                    int(experience_years) if experience_years else 0,
                                    float(consultation_fee) if consultation_fee else 0.0)
            
            # Update session name if changed
            session['full_name'] = full_name
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'danger')
            return redirect(url_for('auth.edit_profile'))
    
    # GET request - show edit form
    if role == 'PATIENT':
        user_data = get_patient_details(user_id)
    else:
        user_data = get_doctor_details(user_id)
    
    return render_template('edit_profile.html', user=user_data, role=role)
