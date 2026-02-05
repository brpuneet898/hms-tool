"""
Medication Reminder Scheduler Service
Sends daily email reminders to patients about their medications
"""
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from database import execute_query, get_ist_today, get_ist_now
import json


mail = None  # Will be initialized in app.py


def send_followup_appointment_reminders():
    """
    Send email reminders for follow-up appointments scheduled for today
    Runs daily at 7:00 AM IST
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    
    # Get all follow-up appointments scheduled for today
    query = """
        SELECT 
            a.id as appointment_id,
            a.time as appointment_time,
            a.consultation_mode,
            a.meet_link,
            u.id as patient_id,
            u.full_name as patient_name,
            u.email as patient_email,
            d.full_name as doctor_name,
            dd.specialization,
            dd.clinic_address
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        JOIN users d ON a.doctor_id = d.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.follow_up_date = ?
        AND a.follow_up_required = 1
        AND a.status = 'COMPLETED'
    """
    
    appointments = execute_query(query, (today,), fetchall=True)
    
    if not appointments:
        print(f"📭 No follow-up appointment reminders to send today ({today})")
        return
    
    print(f"📬 Sending {len(appointments)} follow-up appointment reminders...")
    
    for appt in appointments:
        try:
            send_followup_email(
                patient_name=appt['patient_name'],
                patient_email=appt['patient_email'],
                doctor_name=appt['doctor_name'],
                specialization=appt['specialization'],
                appointment_time=appt['appointment_time'],
                consultation_mode=appt['consultation_mode'],
                meet_link=appt['meet_link'],
                clinic_address=appt['clinic_address']
            )
            
            print(f"✅ Sent follow-up reminder to {appt['patient_email']}")
            
        except Exception as e:
            print(f"❌ Failed to send follow-up reminder to {appt['patient_email']}: {e}")


def send_followup_email(patient_name, patient_email, doctor_name, specialization, 
                        appointment_time, consultation_mode, meet_link, clinic_address):
    """
    Send formatted follow-up appointment reminder email
    """
    today_formatted = get_ist_now().strftime('%A, %B %d, %Y')
    
    # Build email HTML
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                       color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .appointment-card {{ background: white; padding: 25px; margin: 20px 0; 
                                border-left: 5px solid #f5576c; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .detail-row {{ margin: 12px 0; padding: 10px; background: #fff5f7; border-radius: 5px; }}
            .label {{ font-weight: bold; color: #f5576c; display: inline-block; min-width: 140px; }}
            .value {{ color: #333; }}
            .cta-button {{ display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                          color: white; text-decoration: none; border-radius: 25px; margin-top: 20px; 
                          font-weight: bold; text-align: center; }}
            .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 0.9em; }}
            .icon {{ font-size: 1.2em; margin-right: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📅 Follow-Up Appointment Reminder</h1>
                <p style="font-size: 1.1em; margin-top: 10px;">Your appointment is today!</p>
            </div>
            <div class="content">
                <p>Hello <strong>{patient_name}</strong>,</p>
                <p>This is a friendly reminder about your follow-up appointment scheduled for <strong>today</strong>.</p>
                
                <div class="appointment-card">
                    <h3 style="margin-top: 0; color: #f5576c;">🩺 Appointment Details</h3>
                    
                    <div class="detail-row">
                        <span class="label">📅 Date:</span>
                        <span class="value">{today_formatted}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">🕐 Time:</span>
                        <span class="value">{appointment_time}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">👨‍⚕️ Doctor:</span>
                        <span class="value">Dr. {doctor_name}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">🏥 Specialization:</span>
                        <span class="value">{specialization if specialization else 'General'}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">💻 Mode:</span>
                        <span class="value">{consultation_mode if consultation_mode else 'In-Person'}</span>
                    </div>
    """
    
    if consultation_mode == 'ONLINE' and meet_link:
        html_body += f"""
                    <div class="detail-row">
                        <span class="label">🔗 Meeting Link:</span>
                        <span class="value"><a href="{meet_link}" style="color: #f5576c;">{meet_link}</a></span>
                    </div>
        """
    
    if clinic_address and consultation_mode != 'ONLINE':
        html_body += f"""
                    <div class="detail-row">
                        <span class="label">📍 Location:</span>
                        <span class="value">{clinic_address}</span>
                    </div>
        """
    
    html_body += """
                </div>
                
                <p style="margin-top: 25px; padding: 15px; background: #fff5f7; border-radius: 8px; border-left: 4px solid #f5576c;">
                    <strong>💡 Reminder:</strong> Please arrive 10 minutes early for your appointment. 
                    If you need to reschedule or cancel, please contact your doctor as soon as possible.
                </p>
                
                <div class="footer">
                    <p>Take care and see you soon! 💚</p>
                    <p><em>This is an automated reminder from MediFriend</em></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email
    msg = Message(
        subject=f"🩺 Follow-Up Appointment Reminder - Today at {appointment_time}",
        recipients=[patient_email],
        html=html_body
    )
    
    mail.send(msg)


def send_appointment_reminders():
    """
    Send email reminders for confirmed appointments scheduled for today
    Runs daily at 8:00 AM IST
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    
    # Get all confirmed appointments scheduled for today
    query = """
        SELECT 
            a.id as appointment_id,
            a.time as appointment_time,
            a.consultation_mode,
            a.meet_link,
            a.symptoms,
            a.was_rescheduled,
            a.original_date,
            a.original_time,
            u.id as patient_id,
            u.full_name as patient_name,
            u.email as patient_email,
            d.full_name as doctor_name,
            dd.specialization,
            dd.clinic_address,
            dd.consultation_fee
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        JOIN users d ON a.doctor_id = d.id
        LEFT JOIN doctor_details dd ON a.doctor_id = dd.user_id
        WHERE a.date = ?
        AND a.status = 'CONFIRMED'
    """
    
    appointments = execute_query(query, (today,), fetchall=True)
    
    if not appointments:
        print(f"📭 No appointment reminders to send today ({today})")
        return
    
    print(f"📬 Sending {len(appointments)} appointment reminders...")
    
    for appt in appointments:
        try:
            send_appointment_email(
                patient_name=appt['patient_name'],
                patient_email=appt['patient_email'],
                doctor_name=appt['doctor_name'],
                specialization=appt['specialization'],
                appointment_time=appt['appointment_time'],
                consultation_mode=appt['consultation_mode'],
                meet_link=appt['meet_link'],
                clinic_address=appt['clinic_address'],
                was_rescheduled=appt.get('was_rescheduled', 0),
                original_date=appt.get('original_date'),
                original_time=appt.get('original_time')
            )
            
            print(f"✅ Sent appointment reminder to {appt['patient_email']}")
            
        except Exception as e:
            print(f"❌ Failed to send appointment reminder to {appt['patient_email']}: {e}")


def send_appointment_email(patient_name, patient_email, doctor_name, specialization, 
                           appointment_time, consultation_mode, meet_link, clinic_address,
                           was_rescheduled=0, original_date=None, original_time=None):
    """
    Send formatted appointment reminder email
    """
    today_formatted = get_ist_now().strftime('%A, %B %d, %Y')
    
    # Build email HTML
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .appointment-card {{ background: white; padding: 25px; margin: 20px 0; 
                                border-left: 5px solid #764ba2; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .detail-row {{ margin: 12px 0; padding: 10px; background: #f0f4ff; border-radius: 5px; }}
            .label {{ font-weight: bold; color: #667eea; display: inline-block; min-width: 140px; }}
            .value {{ color: #333; }}
            .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 0.9em; }}
            .icon {{ font-size: 1.2em; margin-right: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📅 Appointment Reminder</h1>
                <p style="font-size: 1.1em; margin-top: 10px;">Your appointment is today!</p>
            </div>
            <div class="content">
                <p>Hello <strong>{patient_name}</strong>,</p>
                <p>This is a friendly reminder about your appointment scheduled for <strong>today</strong>.</p>
                
                <div class="appointment-card">
                    <h3 style="margin-top: 0; color: #667eea;">🩺 Appointment Details</h3>
    """
    
    if was_rescheduled:
        html_body += f"""
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; 
                                padding: 8px 15px; border-radius: 5px; display: inline-block; margin-bottom: 15px; font-weight: bold;">
                        📅 Rescheduled Appointment
                    </div>
                    <div style="background: linear-gradient(135deg, #fff5e6 0%, #ffe6f0 100%); 
                                padding: 10px 15px; border-radius: 8px; border-left: 4px solid #f5576c; margin-bottom: 15px;">
                        <strong style="color: #f5576c;">ℹ️ Note:</strong> This appointment was rescheduled from {original_date} at {original_time}
                    </div>
        """
    
    html_body += f"""
                    
                    <div class="detail-row">
                        <span class="label">📅 Date:</span>
                        <span class="value">{today_formatted}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">🕐 Time:</span>
                        <span class="value">{appointment_time}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">👨‍⚕️ Doctor:</span>
                        <span class="value">Dr. {doctor_name}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">🏥 Specialization:</span>
                        <span class="value">{specialization if specialization else 'General'}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">💻 Mode:</span>
                        <span class="value">{consultation_mode if consultation_mode else 'In-Person'}</span>
                    </div>
    """
    
    if consultation_mode == 'ONLINE' and meet_link:
        html_body += f"""
                    <div class="detail-row">
                        <span class="label">🔗 Meeting Link:</span>
                        <span class="value"><a href="{meet_link}" style="color: #667eea;">{meet_link}</a></span>
                    </div>
        """
    
    if clinic_address and consultation_mode != 'ONLINE':
        html_body += f"""
                    <div class="detail-row">
                        <span class="label">📍 Location:</span>
                        <span class="value">{clinic_address}</span>
                    </div>
        """
    
    html_body += """
                </div>
                
                <p style="margin-top: 25px; padding: 15px; background: #f0f4ff; border-radius: 8px; border-left: 4px solid #667eea;">
                    <strong>💡 Reminder:</strong> Please arrive 10 minutes early for your appointment. 
                    If you need to reschedule or cancel, please contact your doctor as soon as possible.
                </p>
                
                <div class="footer">
                    <p>Take care and see you soon! 💚</p>
                    <p><em>This is an automated reminder from MediFriend</em></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email
    msg = Message(
        subject=f"🩺 Appointment Reminder - Today at {appointment_time}",
        recipients=[patient_email],
        html=html_body
    )
    
    mail.send(msg)


def init_scheduler(app):
    """Initialize the APScheduler with Flask app"""
    global mail
    from flask_mail import Mail
    mail = Mail(app)
    
    scheduler = BackgroundScheduler()
    
    # Schedule follow-up appointment reminders at 7:00 AM IST
    scheduler.add_job(
        func=send_followup_appointment_reminders,
        trigger='cron',
        hour=7,
        minute=0,
        id='followup_appointment_reminder',
        name='Send follow-up appointment reminders',
        replace_existing=True
    )
    
    # Schedule appointment reminders at 8:00 AM IST
    scheduler.add_job(
        func=send_appointment_reminders,
        trigger='cron',
        hour=8,
        minute=0,
        id='appointment_reminder',
        name='Send appointment reminders',
        replace_existing=True
    )
    
    # Schedule daily medication reminders at 8:30 AM IST
    scheduler.add_job(
        func=send_daily_medication_reminders,
        trigger='cron',
        hour=8,
        minute=30,
        id='daily_medication_reminder',
        name='Send daily medication reminders',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Appointment & medication reminder scheduler started!")
    
    return scheduler


def send_daily_medication_reminders():
    """
    Main job that runs daily at 8 AM
    Sends ONE email per patient with ALL their active medications
    """
    today = get_ist_today().strftime('%Y-%m-%d')
    
    # Get all active reminders for today
    query = """
        SELECT mr.id as reminder_id, mr.patient_id, mr.prescription_id, mr.last_sent_date,
               u.full_name, u.email,
               p.medicines_json, p.diagnosis, p.created_at
        FROM medication_reminders mr
        JOIN users u ON mr.patient_id = u.id
        JOIN prescriptions p ON mr.prescription_id = p.id
        WHERE mr.is_active = 1
        AND mr.start_date <= ?
        AND mr.end_date >= ?
        AND (mr.last_sent_date IS NULL OR mr.last_sent_date < ?)
        ORDER BY mr.patient_id, p.created_at
    """
    
    reminders = execute_query(query, (today, today, today), fetchall=True)
    
    if not reminders:
        print(f"📭 No medication reminders to send today ({today})")
        return
    
    # Group reminders by patient (ONE email per patient with ALL their medicines)
    patients_data = {}
    reminder_ids = []
    
    for reminder in reminders:
        patient_id = reminder['patient_id']
        
        if patient_id not in patients_data:
            patients_data[patient_id] = {
                'name': reminder['full_name'],
                'email': reminder['email'],
                'medicines': []
            }
        
        # Parse and add medicines from this prescription
        try:
            medicines = json.loads(reminder['medicines_json'])
            if medicines:
                patients_data[patient_id]['medicines'].extend(medicines)
        except:
            pass
        
        # Track reminder IDs to update later
        reminder_ids.append(reminder['reminder_id'])
    
    print(f"📬 Sending medication reminders to {len(patients_data)} patients...")
    
    # Send ONE email per patient with ALL their medicines
    for patient_id, data in patients_data.items():
        try:
            if data['medicines']:  # Only send if patient has medicines
                send_medication_email(
                    patient_name=data['name'],
                    patient_email=data['email'],
                    all_medicines=data['medicines']
                )
                
                print(f"✅ Sent reminder to {data['email']} ({len(data['medicines'])} medicines)")
        except Exception as e:
            print(f"❌ Failed to send reminder to {data['email']}: {e}")
    
    # Update last_sent_date for ALL reminders
    if reminder_ids:
        placeholders = ','.join(['?' for _ in reminder_ids])
        update_query = f"""
            UPDATE medication_reminders
            SET last_sent_date = ?
            WHERE id IN ({placeholders})
        """
        execute_query(update_query, (today, *reminder_ids), commit=True)


def send_medication_email(patient_name, patient_email, all_medicines):
    """
    Send formatted medication reminder email to patient
    Combines ALL medicines from ALL active prescriptions
    """
    if not all_medicines:
        return
    
    # Group medicines by timing
    morning_meds = []
    afternoon_meds = []
    evening_meds = []
    night_meds = []
    anytime_meds = []
    
    for med in all_medicines:
        timing = med.get('timing', '').lower()
        food = med.get('food', '')
        
        med_info = {
            'name': med.get('name', 'Unknown'),
            'dosage': med.get('dosage', ''),
            'food': food
        }
        
        if 'morning' in timing:
            morning_meds.append(med_info)
        if 'afternoon' in timing:
            afternoon_meds.append(med_info)
        if 'evening' in timing:
            evening_meds.append(med_info)
        if 'night' in timing:
            night_meds.append(med_info)
        
        # If no specific timing, add to anytime
        if not timing or timing == '-':
            anytime_meds.append(med_info)
    
    # Build email HTML
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .medicine-section {{ background: white; padding: 20px; margin: 15px 0; 
                                border-left: 4px solid #667eea; border-radius: 8px; }}
            .medicine-section h3 {{ margin-top: 0; color: #667eea; }}
            .medicine-item {{ margin: 10px 0; padding: 10px; background: #f0f4ff; border-radius: 5px; }}
            .medicine-name {{ font-weight: bold; color: #333; }}
            .medicine-details {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #888; font-size: 0.9em; }}
            .icon {{ font-size: 1.2em; margin-right: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🩺 Your Medicine Reminder</h1>
                <p>{get_ist_now().strftime('%A, %B %d, %Y')}</p>
            </div>
            <div class="content">
                <p>Hello <strong>{patient_name}</strong>,</p>
                <p>Here are your medications for today:</p>
    """
    
    # Add morning medicines
    if morning_meds:
        html_body += """
                <div class="medicine-section">
                    <h3>☀️ Morning</h3>
        """
        for med in morning_meds:
            html_body += f"""
                    <div class="medicine-item">
                        <div class="medicine-name">💊 {med['name']} {med['dosage']}</div>
                        <div class="medicine-details">{med['food'] if med['food'] else ''}</div>
                    </div>
            """
        html_body += "</div>"
    
    # Add afternoon medicines
    if afternoon_meds:
        html_body += """
                <div class="medicine-section">
                    <h3>🌤️ Afternoon</h3>
        """
        for med in afternoon_meds:
            html_body += f"""
                    <div class="medicine-item">
                        <div class="medicine-name">💊 {med['name']} {med['dosage']}</div>
                        <div class="medicine-details">{med['food'] if med['food'] else ''}</div>
                    </div>
            """
        html_body += "</div>"
    
    # Add evening medicines
    if evening_meds:
        html_body += """
                <div class="medicine-section">
                    <h3>🌅 Evening</h3>
        """
        for med in evening_meds:
            html_body += f"""
                    <div class="medicine-item">
                        <div class="medicine-name">💊 {med['name']} {med['dosage']}</div>
                        <div class="medicine-details">{med['food'] if med['food'] else ''}</div>
                    </div>
            """
        html_body += "</div>"
    
    # Add night medicines
    if night_meds:
        html_body += """
                <div class="medicine-section">
                    <h3>🌙 Night</h3>
        """
        for med in night_meds:
            html_body += f"""
                    <div class="medicine-item">
                        <div class="medicine-name">💊 {med['name']} {med['dosage']}</div>
                        <div class="medicine-details">{med['food'] if med['food'] else ''}</div>
                    </div>
            """
        html_body += "</div>"
    
    # Add anytime medicines
    if anytime_meds:
        html_body += """
                <div class="medicine-section">
                    <h3>⏰ Anytime</h3>
        """
        for med in anytime_meds:
            html_body += f"""
                    <div class="medicine-item">
                        <div class="medicine-name">💊 {med['name']} {med['dosage']}</div>
                        <div class="medicine-details">{med['food'] if med['food'] else ''}</div>
                    </div>
            """
        html_body += "</div>"
    
    html_body += f"""
                <div class="footer">
                    <p>Stay healthy and take care! 💚</p>
                    <p><em>This is an automated reminder from MediFriend</em></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email
    msg = Message(
        subject=f"🩺 Your Medicine Reminder - {get_ist_now().strftime('%B %d, %Y')}",
        recipients=[patient_email],
        html=html_body
    )
    
    mail.send(msg)


def create_medication_reminder(prescription_id, patient_id, max_duration_days):
    """
    Create a medication reminder entry when prescription is created
    Called from routes/doctor.py after prescription creation
    """
    start_date = get_ist_today().strftime('%Y-%m-%d')
    end_date = (get_ist_today() + timedelta(days=max_duration_days)).strftime('%Y-%m-%d')
    
    query = """
        INSERT INTO medication_reminders (prescription_id, patient_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, 1)
    """
    
    return execute_query(query, (prescription_id, patient_id, start_date, end_date), commit=True)


def deactivate_medication_reminder(prescription_id):
    """
    Deactivate medication reminder (e.g., when prescription is completed)
    """
    query = """
        UPDATE medication_reminders
        SET is_active = 0
        WHERE prescription_id = ?
    """
    
    return execute_query(query, (prescription_id,), commit=True)
