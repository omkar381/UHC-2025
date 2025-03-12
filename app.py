from flask import Flask, render_template, request, redirect, url_for, send_file, make_response, jsonify, flash
import os
import qrcode
import base64
import uuid
import re
import random
import string
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
import json

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Try to import pdfkit, but provide alternative if not available
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False

# Try to import PIL for alternative PDF generation
try:
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__)

# Get the application root directory
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Define directories relative to the app root
QR_FOLDER = os.path.join(APP_ROOT, "static", "qr_codes")
PHOTO_FOLDER = os.path.join(APP_ROOT, "static", "user_photos")
PDF_FOLDER = os.path.join(APP_ROOT, "static", "pdf_cards")

# Create necessary directories
for directory in [QR_FOLDER, PHOTO_FOLDER, PDF_FOLDER]:
    os.makedirs(directory, exist_ok=True)

# Define data file paths
USERS_FILE = os.path.join(APP_ROOT, "users_data.json")
HOSPITALS_FILE = os.path.join(APP_ROOT, "hospitals_data.json")
MEDICAL_RECORDS_FILE = os.path.join(APP_ROOT, "medical_records.json")

# Initialize empty data structures
users = {}
hospitals = {}
medical_records = {}

# Dictionary to store verification IDs and their associated data
verification_data = {}

# Function to ensure data files exist
def ensure_data_files():
    for file_path, data in [
        (USERS_FILE, users),
        (HOSPITALS_FILE, hospitals),
        (MEDICAL_RECORDS_FILE, medical_records)
    ]:
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(data, f)

# Create data files if they don't exist
ensure_data_files()

# Load existing data
def load_data():
    global users, hospitals, medical_records
    
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
    except Exception as e:
        print(f"Error loading users data: {e}")
        users = {}
        
    try:
        if os.path.exists(HOSPITALS_FILE):
            with open(HOSPITALS_FILE, 'r') as f:
                hospitals = json.load(f)
    except Exception as e:
        print(f"Error loading hospitals data: {e}")
        hospitals = {}
        
    try:
        if os.path.exists(MEDICAL_RECORDS_FILE):
            with open(MEDICAL_RECORDS_FILE, 'r') as f:
                medical_records = json.load(f)
    except Exception as e:
        print(f"Error loading medical records: {e}")
        medical_records = {}

# Load data at startup
load_data()

# Function to save users data
def save_users_data():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving users data: {e}")

# Generate UIN (Unique Identification Number)
def generate_uin():
    # Format: UIN-YYYYMMDD-XXXX (where XXXX is a random alphanumeric string)
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"UIN-{date_part}-{random_part}"

# Function to generate PDF using ReportLab (alternative to pdfkit)
def generate_pdf_with_reportlab(user_data, unique_id):
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        # Create PDF filename
        pdf_filename = f"health_card_{unique_id}.pdf"
        pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
        
        # Create a PDF document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Create custom styles
        uin_style = ParagraphStyle(
            'UINStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            backColor=colors.lightblue,
            borderColor=colors.blue,
            borderWidth=1,
            borderPadding=5,
            borderRadius=5,
            spaceAfter=10
        )
        
        # Build the PDF content
        content = []
        
        # Title
        content.append(Paragraph("UNIVERSAL HEALTH CARD", title_style))
        content.append(Spacer(1, 12))
        
        # Add user photo if available
        if user_data.get('photo_path'):
            try:
                img_path = os.path.join('backend', 'static', user_data['photo_path'])
                img = ReportLabImage(img_path, width=2*inch, height=2.5*inch)
                content.append(img)
                content.append(Spacer(1, 12))
            except:
                # If image loading fails, continue without the image
                pass
        
        # Add UIN with special styling
        content.append(Paragraph(f"UIN: {user_data.get('uin', 'N/A')}", uin_style))
        content.append(Spacer(1, 12))
        
        # Personal Information
        content.append(Paragraph("Personal Information", heading_style))
        content.append(Paragraph(f"<b>Name:</b> {user_data.get('name', 'N/A')}", normal_style))
        content.append(Paragraph(f"<b>Date of Birth:</b> {user_data.get('dob', 'N/A')}", normal_style))
        content.append(Paragraph(f"<b>Address:</b> {user_data.get('address', 'N/A')}", normal_style))
        content.append(Paragraph(f"<b>Phone:</b> {user_data.get('phone', 'N/A')}", normal_style))
        content.append(Paragraph(f"<b>Email:</b> {user_data.get('email', 'N/A')}", normal_style))
        content.append(Spacer(1, 12))
        
        # Card Information
        content.append(Paragraph("Card Information", heading_style))
        content.append(Paragraph(f"<b>Card ID:</b> {unique_id}", normal_style))
        content.append(Paragraph(f"<b>Issue Date:</b> {user_data.get('created_at', 'N/A')}", normal_style))
        content.append(Paragraph(f"<b>Expiry Date:</b> {user_data.get('expiry_date', 'N/A')}", normal_style))
        content.append(Spacer(1, 24))
        
        # Important Information
        content.append(Paragraph("Important Information", heading_style))
        content.append(Paragraph("This card is the property of the Universal Health Program.", normal_style))
        content.append(Paragraph("If found, please return to the nearest health center.", normal_style))
        content.append(Paragraph("This card must be presented when seeking healthcare services.", normal_style))
        content.append(Paragraph(f"For verification, visit our website and enter your UIN: {user_data.get('uin', 'N/A')}", normal_style))
        
        # Build the PDF
        doc.build(content)
        
        return pdf_path
    
    except Exception as e:
        print(f"Error generating PDF with ReportLab: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        uin = request.form.get('uin')
        password = request.form.get('password')
        
        if not uin or not password:
            return jsonify({'verified': False, 'message': 'UIN and password are required'})
        
        # Hash the password for comparison
        hashed_password = hash_password(password)
        
        # Find user by UIN
        for unique_id, user_data in users.items():
            if user_data.get('uin') == uin:
                # Verify password
                if user_data.get('password') == hashed_password:
                    return jsonify({
                        'verified': True,
                        'unique_id': unique_id
                    })
                else:
                    return jsonify({
                        'verified': False,
                        'message': 'Invalid password'
                    })
        
        return jsonify({'verified': False, 'message': 'Invalid UIN'})
    
    return render_template('user_login.html')

@app.route('/register', methods=['GET'])
def show_register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        # Get form data safely
        name = request.form.get('name', '').strip()
        dob = request.form.get('dob', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        photo_data = request.form.get('photo_data', '')

        # Validation: Ensure all fields are filled
        if not all([name, dob, address, phone, email, password, photo_data]):
            return jsonify({
                'status': 'error',
                'message': 'All fields are required including photo and password!'
            }), 400

        # Generate Unique ID with timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        unique_id = f"UHC-{timestamp}-{str(uuid.uuid4())[:8]}"
        
        # Generate UIN
        uin = generate_uin()

        # Process and save the photo
        photo_path = None
        if photo_data and photo_data.startswith('data:image'):
            # Extract the base64 encoded image
            image_data = re.sub('^data:image/.+;base64,', '', photo_data)
            image_bytes = base64.b64decode(image_data)
            
            # Save the image
            photo_filename = f"{unique_id}.jpg"
            photo_full_path = os.path.join(PHOTO_FOLDER, photo_filename)
            
            with open(photo_full_path, 'wb') as f:
                f.write(image_bytes)
            
            # Store relative path for database - use the correct path format for templates
            photo_path = f"user_photos/{photo_filename}"

        # Generate QR Code
        qr_filename = f"{unique_id}.png"
        qr_full_path = os.path.join(QR_FOLDER, qr_filename)
        
        # Include more information in QR code
        qr_data = f"ID: {unique_id}\nUIN: {uin}\nName: {name}\nDOB: {dob}\nContact: {phone}"
        qr = qrcode.make(qr_data)
        qr.save(qr_full_path)
        
        # Store relative path for database - use the correct path format for templates
        qr_path = f"qr_codes/{qr_filename}"

        # Calculate expiry date (5 years from now)
        expiry_date = (datetime.now() + timedelta(days=5*365)).strftime("%Y-%m-%d")

        # Hash the password before storing
        hashed_password = hash_password(password)

        # Store user details
        users[unique_id] = {
            'first_name': name.split()[0] if ' ' in name else name,
            'last_name': ' '.join(name.split()[1:]) if ' ' in name else '',
            'date_of_birth': dob, 
            'address': address,
            'phone': phone,
            'email': email,
            'password': hashed_password,
            'uin': uin,
            'photo_path': photo_path,
            'qr_path': qr_path,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'expiry_date': expiry_date,
            'verification_history': []
        }
        
        # Save users data to file
        save_users_data()

        # Return a success response with the unique_id
        return jsonify({
            'status': 'success',
            'unique_id': unique_id,
            'message': 'Registration successful'
        })

    except Exception as e:
        print(f"Error in registration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/registration_status/<unique_id>')
def registration_status(unique_id):
    user = users.get(unique_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    return jsonify({'status': 'success', 'redirect_url': url_for('success', unique_id=unique_id)})

@app.route('/generate_certificate/<record_id>/<unique_id>')
def generate_certificate(record_id, unique_id):
    try:
        user = users.get(unique_id)
        if not user:
            return "User not found!", 404

        # Find the medical record
        user_records = medical_records.get(user['uin'], [])
        record = None
        for r in user_records:
            if r.get('record_id') == record_id:
                record = r
                break

        if not record:
            return "Medical record not found!", 404

        # Create directories for storing generated files if they don't exist
        os.makedirs('static/images', exist_ok=True)
        
        # Add insurance information if not present
        if 'insurance_provider' not in user:
            user['insurance_provider'] = record.get('insurance_provider', 'Not Available')
        if 'policy_number' not in user:
            user['policy_number'] = record.get('policy_number', 'Not Available')
        if 'coverage_type' not in user:
            user['coverage_type'] = record.get('coverage_type', 'Not Available')
        if 'insurance_valid_until' not in user:
            user['insurance_valid_until'] = record.get('insurance_valid_until', 'Not Available')
        
        # Create medication schedule
        medications = []
        if record.get('medicines'):
            # Parse medicines from the record
            medicine_list = record.get('medicines', '').split('\n')
            for i, med in enumerate(medicine_list):
                if med.strip():
                    # Create a medication object with default values
                    medication = {
                        'name': med.strip(),
                        'dosage': record.get(f'med_{i}_dosage', 'As directed'),
                        'frequency': record.get(f'med_{i}_frequency', 'As needed'),
                        'duration': record.get(f'med_{i}_duration', 'Until symptoms resolve'),
                        'instructions': record.get(f'med_{i}_instructions', '')
                    }
                    medications.append(medication)
        
        # Create follow-up appointments
        appointments = []
        if record.get('follow_up_date'):
            appointment = {
                'date': record.get('follow_up_date', ''),
                'time': record.get('follow_up_time', ''),
                'doctor': f"Dr. {record.get('doctor_name', '')}",
                'purpose': record.get('follow_up_purpose', 'Follow-up consultation'),
                'location': record.get('hospital_name', '')
            }
            appointments.append(appointment)
        
        # Get treatment history from the record or create from previous records
        treatment_history = []
        
        # First check if the record has treatment history data
        if record.get('treatment_history'):
            treatment_history = record.get('treatment_history')
        else:
            # Create treatment history from previous records
            for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
                if r.get('record_id') != record_id:  # Exclude current record
                    treatment = {
                        'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                        'title': r.get('diagnosis', 'Medical Visit'),
                        'description': f"Treatment: {r.get('treatment', 'Not specified')}"
                    }
                    treatment_history.append(treatment)
                    if len(treatment_history) >= 5:  # Limit to 5 previous treatments
                        break
        
        # Get certificate history from the record or create from previous records
        certificate_history = []
        
        # First check if the record has certificate history data
        if record.get('certificate_history'):
            certificate_history = record.get('certificate_history')
            # Add links to certificates
            for cert in certificate_history:
                if 'link' not in cert:
                    cert['link'] = '#'  # Placeholder link if not provided
        else:
            # Create certificate history from previous records
            for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
                if r.get('record_id') != record_id:  # Exclude current record
                    cert = {
                        'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                        'type': 'Medical Certificate',
                        'doctor': f"Dr. {r.get('doctor_name', '')}",
                        'purpose': r.get('diagnosis', 'Medical Documentation'),
                        'link': url_for('generate_certificate', record_id=r.get('record_id'), unique_id=unique_id)
                    }
                    certificate_history.append(cert)
                    if len(certificate_history) >= 3:  # Limit to 3 previous certificates
                        break

        # First try to render the certificate as HTML
        try:
            return render_template('medical_certificate.html', 
                                  user=user, 
                                  record=record,
                                  medications=medications,
                                  appointments=appointments,
                                  treatment_history=treatment_history,
                                  certificate_history=certificate_history)
        except Exception as e:
            print(f"Error rendering certificate HTML: {str(e)}")
            
            # If HTML rendering fails, generate PDF
            try:
                # Generate PDF filename
                pdf_filename = f"medical_certificate_{record_id}.pdf"
                pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
                
                if PDFKIT_AVAILABLE:
                    # Generate HTML content
                    html = render_template('medical_certificate.html', 
                                          user=user, 
                                          record=record,
                                          medications=medications,
                                          appointments=appointments,
                                          treatment_history=treatment_history,
                                          certificate_history=certificate_history)
                    
                    # PDF options for better quality
                    options = {
                        'page-size': 'A4',
                        'margin-top': '0mm',
                        'margin-right': '0mm',
                        'margin-bottom': '0mm',
                        'margin-left': '0mm',
                        'encoding': 'UTF-8',
                        'no-outline': None,
                        'enable-local-file-access': None,
                        'title': f'Medical Certificate - {user["first_name"]} {user["last_name"]}',
                        'footer-right': '[page] of [topage]',
                        'footer-font-size': '8',
                        'header-html': render_template('certificate_header.html', hospital_name=record['hospital_name']),
                        'header-spacing': '5'
                    }
                    
                    # Create PDF
                    pdfkit.from_string(html, pdf_path, options=options)
                elif REPORTLAB_AVAILABLE:
                    # Use ReportLab as fallback
                    generate_certificate_with_reportlab(user, record, pdf_path)
                else:
                    return "PDF generation is not available.", 500

                return send_file(
                    pdf_path,
                    as_attachment=True,
                    download_name=f"medical_certificate_{record_id}.pdf"
                )

            except Exception as e:
                print(f"Error generating certificate PDF: {str(e)}")
                return f"Error generating certificate: {str(e)}", 500

    except Exception as e:
        print(f"Error in generate_certificate: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/download_certificate/<record_id>/<unique_id>')
def download_certificate(record_id, unique_id):
    try:
        user = users.get(unique_id)
        if not user:
            return "User not found!", 404

        # Find the medical record
        user_records = medical_records.get(user['uin'], [])
        record = None
        for r in user_records:
            if r.get('record_id') == record_id:
                record = r
                break

        if not record:
            return "Medical record not found!", 404

        # Add insurance information if not present
        if 'insurance_provider' not in user:
            user['insurance_provider'] = record.get('insurance_provider', 'Not Available')
        if 'policy_number' not in user:
            user['policy_number'] = record.get('policy_number', 'Not Available')
        if 'coverage_type' not in user:
            user['coverage_type'] = record.get('coverage_type', 'Not Available')
        if 'insurance_valid_until' not in user:
            user['insurance_valid_until'] = record.get('insurance_valid_until', 'Not Available')
        
        # Create medication schedule
        medications = []
        if record.get('medicines'):
            # Parse medicines from the record
            medicine_list = record.get('medicines', '').split('\n')
            for i, med in enumerate(medicine_list):
                if med.strip():
                    # Create a medication object with default values
                    medication = {
                        'name': med.strip(),
                        'dosage': record.get(f'med_{i}_dosage', 'As directed'),
                        'frequency': record.get(f'med_{i}_frequency', 'As needed'),
                        'duration': record.get(f'med_{i}_duration', 'Until symptoms resolve'),
                        'instructions': record.get(f'med_{i}_instructions', '')
                    }
                    medications.append(medication)
        
        # Create follow-up appointments
        appointments = []
        if record.get('follow_up_date'):
            appointment = {
                'date': record.get('follow_up_date', ''),
                'time': record.get('follow_up_time', ''),
                'doctor': f"Dr. {record.get('doctor_name', '')}",
                'purpose': record.get('follow_up_purpose', 'Follow-up consultation'),
                'location': record.get('hospital_name', '')
            }
            appointments.append(appointment)
        
        # Create treatment history from previous records
        treatment_history = []
        for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
            if r.get('record_id') != record_id:  # Exclude current record
                treatment = {
                    'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                    'title': r.get('diagnosis', 'Medical Visit'),
                    'description': f"Treatment: {r.get('treatment', 'Not specified')}"
                }
                treatment_history.append(treatment)
                if len(treatment_history) >= 5:  # Limit to 5 previous treatments
                    break
        
        # Create certificate history
        certificate_history = []
        for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
            if r.get('record_id') != record_id:  # Exclude current record
                cert = {
                    'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                    'type': 'Medical Certificate',
                    'doctor': f"Dr. {r.get('doctor_name', '')}",
                    'purpose': r.get('diagnosis', 'Medical Documentation'),
                    'link': url_for('generate_certificate', record_id=r.get('record_id'), unique_id=unique_id)
                }
                certificate_history.append(cert)
                if len(certificate_history) >= 3:  # Limit to 3 previous certificates
                    break

        # Generate PDF filename
        pdf_filename = f"medical_certificate_{record_id}.pdf"
        pdf_path = os.path.join(PDF_FOLDER, pdf_filename)

        # Generate PDF
        if PDFKIT_AVAILABLE:
            html = render_template('medical_certificate.html', 
                                  user=user, 
                                  record=record,
                                  medications=medications,
                                  appointments=appointments,
                                  treatment_history=treatment_history,
                                  certificate_history=certificate_history)
            options = {
                'page-size': 'A4',
                'margin-top': '0mm',
                'margin-right': '0mm',
                'margin-bottom': '0mm',
                'margin-left': '0mm',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None
            }
            pdfkit.from_string(html, pdf_path, options=options)
        elif REPORTLAB_AVAILABLE:
            generate_certificate_with_reportlab(user, record, pdf_path)
        else:
            return "PDF generation is not available.", 500

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"medical_certificate_{record_id}.pdf"
        )

    except Exception as e:
        print(f"Error generating certificate PDF: {str(e)}")
        return f"Error generating certificate: {str(e)}", 500

@app.route('/success/<unique_id>')
def success(unique_id):
    user = users.get(unique_id)
    if not user:
        return "User not found!", 404
    
    # Get the first and last name
    first_name = user.get('first_name', '')
    last_name = user.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()
    
    # Ensure photo and QR paths are correct for templates
    photo_path = user.get('photo_path', '')
    if photo_path:
        photo_path = url_for('static', filename=photo_path)
    
    qr_path = user.get('qr_path', '')
    if qr_path:
        qr_path = url_for('static', filename=qr_path)
    
    return render_template(
        'success.html',
        unique_id=unique_id,
        name=full_name,
        dob=user.get('date_of_birth', ''),
        address=user.get('address', ''),
        phone=user.get('phone', ''),
        email=user.get('email', ''),
        uin=user.get('uin', ''),
        photo_path=photo_path,
        qr_path=qr_path,
        created_at=user.get('created_at', ''),
        expiry_date=user.get('expiry_date', '')
    )

@app.route('/generate_card/<unique_id>')
def generate_card(unique_id):
    user = users.get(unique_id)
    if not user:
        return "User not found!", 404
    
    # Get the first and last name
    first_name = user.get('first_name', '')
    last_name = user.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()
    
    # Ensure photo and QR paths are correct for templates
    photo_path = user.get('photo_path', '')
    if photo_path:
        photo_path = url_for('static', filename=photo_path)
    
    qr_path = user.get('qr_path', '')
    if qr_path:
        qr_path = url_for('static', filename=qr_path)
    
    return render_template(
        'id_card.html',
        unique_id=unique_id,
        name=full_name,
        dob=user.get('date_of_birth', ''),
        address=user.get('address', ''),
        phone=user.get('phone', ''),
        email=user.get('email', ''),
        uin=user.get('uin', ''),
        photo_path=photo_path,
        qr_path=qr_path,
        created_at=user.get('created_at', ''),
        expiry_date=user.get('expiry_date', '')
    )

@app.route('/download_pdf/<unique_id>')
def download_pdf(unique_id):
    user = users.get(unique_id)
    if not user:
        return "User not found!", 404
    
    try:
        pdf_path = None
        
        # Try using pdfkit if available
        if PDFKIT_AVAILABLE:
            try:
                # Generate HTML content
                html = render_template('id_card_pdf.html',
                                      name=user['name'], 
                                      dob=user['dob'], 
                                      address=user['address'],
                                      phone=user.get('phone', 'N/A'),
                                      email=user.get('email', 'N/A'),
                                      uin=user.get('uin', 'N/A'),
                                      unique_id=unique_id,
                                      # Use absolute URLs for PDF generation
                                      qr_path=request.host_url + 'static/' + user['qr_path'],
                                      photo_path=request.host_url + 'static/' + user['photo_path'] if user.get('photo_path') else None,
                                      created_at=user.get('created_at', datetime.now().strftime("%Y-%m-%d")),
                                      expiry_date=user.get('expiry_date', 'N/A'))
                
                # PDF options
                options = {
                    'page-size': 'A4',
                    'margin-top': '0mm',
                    'margin-right': '0mm',
                    'margin-bottom': '0mm',
                    'margin-left': '0mm',
                    'encoding': 'UTF-8',
                    'no-outline': None,
                    'enable-local-file-access': None
                }
                
                # Generate PDF
                pdf_filename = f"health_card_{unique_id}.pdf"
                pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
                
                # Create PDF
                pdfkit.from_string(html, pdf_path, options=options)
            except Exception as e:
                print(f"Error with pdfkit: {str(e)}")
                pdf_path = None
        
        # If pdfkit failed or is not available, try ReportLab
        if pdf_path is None and REPORTLAB_AVAILABLE:
            pdf_path = generate_pdf_with_reportlab(user, unique_id)
        
        # If both methods failed, return an error
        if pdf_path is None:
            return "PDF generation is not available. Please install either pdfkit with wkhtmltopdf or reportlab.", 500
        
        # Return the PDF file
        return send_file(pdf_path, as_attachment=True, download_name=f"health_card_{unique_id}.pdf")
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return f"Error generating PDF: {str(e)}", 500

@app.route('/verify')
def verify_form():
    return render_template('verify.html')

@app.route('/verify_qr', methods=['POST'])
def verify_qr():
    try:
        qr_data = request.json.get('qr_data', '')
        if not qr_data:
            return jsonify({'error': 'No QR data provided'}), 400

        # Parse QR data
        lines = qr_data.split('\n')
        uin = None
        user_data = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if key == 'UIN':
                    uin = value
                user_data[key.lower()] = value

        if not uin:
            return jsonify({'error': 'Invalid QR code format'}), 400

        # Find user by UIN
        found_user = None
        found_id = None
        
        for user_id, stored_user in users.items():
            if stored_user.get('uin') == uin:
                found_user = stored_user
                found_id = user_id
                break

        if found_user:
            # Add verification timestamp
            verification_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Add verification to history (you might want to store this in a database)
            if 'verification_history' not in found_user:
                found_user['verification_history'] = []
            
            found_user['verification_history'].append({
                'timestamp': verification_time,
                'method': 'qr',
                'status': 'success'
            })
            
            # Save updated user data
            save_users_data()
            
            return jsonify({
                'verified': True,
                'user_data': {
                    'name': found_user['name'],
                    'dob': found_user['dob'],
                    'uin': uin,
                    'photo_path': url_for('static', filename=found_user['photo_path']) if found_user.get('photo_path') else None,
                    'verification_time': verification_time,
                    'card_status': 'Active',
                    'expiry_date': found_user.get('expiry_date', 'N/A')
                }
            })
        else:
            return jsonify({
                'verified': False,
                'error': 'Card not found'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/card_analytics')
def card_analytics():
    try:
        total_cards = len(users)
        active_cards = 0
        expired_cards = 0
        verifications_today = 0
        today = datetime.now().date()

        for user in users.values():
            # Check card status
            if 'expiry_date' in user:
                expiry_date = datetime.strptime(user['expiry_date'], "%Y-%m-%d").date()
                if expiry_date >= today:
                    active_cards += 1
                else:
                    expired_cards += 1

            # Count today's verifications
            if 'verification_history' in user:
                for verification in user['verification_history']:
                    verification_date = datetime.strptime(
                        verification['timestamp'], 
                        "%Y-%m-%d %H:%M:%S"
                    ).date()
                    if verification_date == today:
                        verifications_today += 1

        return jsonify({
            'total_cards': total_cards,
            'active_cards': active_cards,
            'expired_cards': expired_cards,
            'verifications_today': verifications_today
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/user_profile/<unique_id>')
def user_profile(unique_id):
    user = users.get(unique_id)
    if not user:
        return "User not found!", 404

    # Get verification history
    verification_history = user.get('verification_history', [])
    
    # Calculate card status
    today = datetime.now().date()
    expiry_date = datetime.strptime(user['expiry_date'], "%Y-%m-%d").date()
    card_status = "Active" if expiry_date >= today else "Expired"
    
    # Calculate days until expiry
    days_until_expiry = (expiry_date - today).days
    
    # Get medical records for the user
    user_medical_records = medical_records.get(user['uin'], [])
    
    return render_template('user_profile.html',
                          user=user,
                          verification_history=verification_history,
                          card_status=card_status,
                          days_until_expiry=days_until_expiry,
                          medical_records=user_medical_records)

@app.route('/download_verification_history/<unique_id>')
def download_verification_history(unique_id):
    user = users.get(unique_id)
    if not user:
        return "User not found!", 404

    # Create CSV data
    output = BytesIO()
    verification_history = user.get('verification_history', [])
    
    # Add headers
    headers = ['Timestamp', 'Method', 'Status']
    csv_data = [headers]
    
    # Add verification records
    for verification in verification_history:
        csv_data.append([
            verification['timestamp'],
            verification['method'],
            verification['status']
        ])
    
    # Write to CSV
    import csv
    writer = csv.writer(output)
    writer.writerows(csv_data)
    
    # Create response
    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'verification_history_{unique_id}.csv'
    )

@app.route('/verify_card', methods=['POST'])
def verify_card():
    uin = request.form.get('uin', '').strip()
    
    # Find user by UIN
    found_user = None
    found_id = None
    
    for user_id, user_data in users.items():
        if user_data.get('uin') == uin:
            found_user = user_data
            found_id = user_id
            break
    
    if found_user:
        # Add verification to history
        verification_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if 'verification_history' not in found_user:
            found_user['verification_history'] = []
        
        found_user['verification_history'].append({
            'timestamp': verification_time,
            'method': 'uin',
            'status': 'success'
        })
        
        # Save updated user data
        save_users_data()
        
        # Calculate card status
        today = datetime.now().date()
        expiry_date = datetime.strptime(found_user['expiry_date'], "%Y-%m-%d").date()
        card_status = "Active" if expiry_date >= today else "Expired"
        
        # Get the full name
        first_name = found_user.get('first_name', '')
        last_name = found_user.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        return render_template('verification_result.html',
                              verified=True,
                              name=full_name,
                              dob=found_user.get('date_of_birth', ''),
                              uin=uin,
                              unique_id=found_id,
                              photo_path=url_for('static', filename=found_user['photo_path']) if found_user.get('photo_path') else None,
                              verification_time=verification_time,
                              card_status=card_status,
                              expiry_date=found_user.get('expiry_date', 'N/A'))
    else:
        return render_template('verification_result.html', verified=False)

# Generate Hospital ID
def generate_hospital_id():
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"HOSP-{date_part}-{random_part}"

# Function to save hospitals data
def save_hospitals_data():
    try:
        with open(HOSPITALS_FILE, 'w') as f:
            json.dump(hospitals, f, indent=4)
    except Exception as e:
        print(f"Error saving hospitals data: {e}")

# Function to save medical records
def save_medical_records():
    try:
        with open(MEDICAL_RECORDS_FILE, 'w') as f:
            json.dump(medical_records, f, indent=4)
    except Exception as e:
        print(f"Error saving medical records: {e}")

@app.route('/hospital_register')
def hospital_register():
    return render_template('hospital_register.html')

@app.route('/register_hospital', methods=['POST'])
def register_hospital():
    try:
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        specialization = request.form.get('specialization', '').strip()
        hospital_type = request.form.get('hospital_type', '').strip()
        license_number = request.form.get('license_number', '').strip()

        if not all([name, address, phone, email, password, specialization, hospital_type, license_number]):
            return "Error: All fields are required!", 400

        hospital_id = generate_hospital_id()

        # Hash the password before storing
        hashed_password = hash_password(password)

        hospitals[hospital_id] = {
            'name': name,
            'address': address,
            'phone': phone,
            'email': email,
            'password': hashed_password,
            'specialization': specialization,
            'hospital_type': hospital_type,
            'license_number': license_number,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'active'
        }

        save_hospitals_data()
        return redirect(url_for('hospital_success', hospital_id=hospital_id))

    except Exception as e:
        print(f"Error in hospital registration: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/hospital_success/<hospital_id>')
def hospital_success(hospital_id):
    hospital = hospitals.get(hospital_id)
    if not hospital:
        return "Hospital not found!", 404
    return render_template('hospital_success.html', hospital=hospital, hospital_id=hospital_id)

@app.route('/hospital_login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == 'POST':
        hospital_id = request.form.get('hospital_id')
        password = request.form.get('password')
        
        if not hospital_id or not password:
            return jsonify({
                'verified': False,
                'message': 'Hospital ID and password are required'
            })
        
        # Hash the password for comparison
        hashed_password = hash_password(password)
        
        # Find hospital by ID
        hospital = hospitals.get(hospital_id)
        if not hospital:
            return jsonify({
                'verified': False,
                'message': 'Invalid Hospital ID'
            })
        
        # Verify password
        if hospital.get('password') == hashed_password:
            return jsonify({
                'verified': True,
                'hospital_id': hospital_id
            })
        else:
            return jsonify({
                'verified': False,
                'message': 'Invalid password'
            })
    
    return render_template('hospital_login.html')

@app.route('/hospital_dashboard/<hospital_id>')
def hospital_dashboard(hospital_id):
    # Debug information
    print(f"Accessing hospital dashboard for ID: {hospital_id}")
    print(f"Available hospital IDs: {list(hospitals.keys())}")
    print(f"Medical records structure: {type(medical_records)}")
    
    # Check if hospital exists
    hospital = hospitals.get(hospital_id)
    if not hospital:
        print(f"Hospital not found with ID: {hospital_id}")
        flash(f'Hospital not found with ID: {hospital_id}', 'error')
        return redirect(url_for('hospital_login'))

    # Add the ID to the hospital object
    hospital['id'] = hospital_id
    print(f"Hospital data: {hospital}")

    # Get all medical records for this hospital
    hospital_records = []
    
    # Debug the structure of medical_records
    for uin, records_list in medical_records.items():
        print(f"UIN: {uin}, Records: {type(records_list)}")
        
        if isinstance(records_list, list):
            for record in records_list:
                if isinstance(record, dict) and record.get('hospital_id') == hospital_id:
                    # Get user details for this record
                    user_id = None
                    # Find user_id by UIN
                    for uid, user_data in users.items():
                        if user_data.get('uin') == uin:
                            user_id = uid
                            break
                    
                    if user_id:
                        user = users.get(user_id)
                        if user:
                            record_with_user = {
                                **record,
                                'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}",
                                'user_uin': uin,
                                'user_dob': user.get('date_of_birth', ''),
                                'user_photo': user.get('photo_path', '')
                            }
                            hospital_records.append(record_with_user)
    
    print(f"Found {len(hospital_records)} records for hospital {hospital_id}")

    return render_template(
        'hospital_dashboard.html',
        hospital=hospital,
        records=hospital_records
    )

@app.route('/add_medical_record', methods=['POST'])
def add_medical_record():
    try:
        # Print form data for debugging
        print("Form data:", request.form)
        
        uin = request.form.get('uin', '').strip()
        hospital_id = request.form.get('hospital_id', '').strip()
        doctor_name = request.form.get('doctor_name', '').strip()
        diagnosis = request.form.get('diagnosis', '').strip()
        treatment = request.form.get('treatment', '').strip()
        medicines = request.form.get('medicines', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Insurance information
        insurance_provider = request.form.get('insurance_provider', '').strip()
        policy_number = request.form.get('policy_number', '').strip()
        coverage_type = request.form.get('coverage_type', '').strip()
        insurance_valid_until = request.form.get('insurance_valid_until', '').strip()
        
        # Follow-up appointment information
        follow_up_date = request.form.get('follow_up_date', '').strip()
        follow_up_time = request.form.get('follow_up_time', '').strip()
        follow_up_purpose = request.form.get('follow_up_purpose', '').strip()
        
        # Medication details
        medicine_list = medicines.split('\n')
        med_details = {}
        for i, med in enumerate(medicine_list):
            if med.strip():
                med_dosage = request.form.get(f'med_{i}_dosage', '').strip()
                med_frequency = request.form.get(f'med_{i}_frequency', '').strip()
                med_duration = request.form.get(f'med_{i}_duration', '').strip()
                med_instructions = request.form.get(f'med_{i}_instructions', '').strip()
                
                if med_dosage:
                    med_details[f'med_{i}_dosage'] = med_dosage
                if med_frequency:
                    med_details[f'med_{i}_frequency'] = med_frequency
                if med_duration:
                    med_details[f'med_{i}_duration'] = med_duration
                if med_instructions:
                    med_details[f'med_{i}_instructions'] = med_instructions
        
        # Treatment history
        treatment_history = []
        i = 0
        while True:
            treatment_date = request.form.get(f'treatment_date_{i}', '').strip()
            treatment_title = request.form.get(f'treatment_title_{i}', '').strip()
            treatment_description = request.form.get(f'treatment_description_{i}', '').strip()
            
            if not treatment_date and not treatment_title:
                break
                
            if treatment_date or treatment_title:
                treatment_history.append({
                    'date': treatment_date,
                    'title': treatment_title,
                    'description': treatment_description
                })
            
            i += 1
        
        # Certificate history
        certificate_history = []
        i = 0
        while True:
            certificate_date = request.form.get(f'certificate_date_{i}', '').strip()
            certificate_type = request.form.get(f'certificate_type_{i}', '').strip()
            certificate_doctor = request.form.get(f'certificate_doctor_{i}', '').strip()
            certificate_purpose = request.form.get(f'certificate_purpose_{i}', '').strip()
            
            if not certificate_date and not certificate_type:
                break
                
            if certificate_date or certificate_type:
                certificate_history.append({
                    'date': certificate_date,
                    'type': certificate_type,
                    'doctor': certificate_doctor,
                    'purpose': certificate_purpose
                })
            
            i += 1
        
        print(f"UIN: {uin}, Hospital ID: {hospital_id}, Doctor: {doctor_name}, Diagnosis: {diagnosis}")

        # Check each required field individually for better error messages
        if not uin:
            return jsonify({'success': False, 'message': 'UIN is required!'})
        if not hospital_id:
            return jsonify({'success': False, 'message': 'Hospital ID is required!'})
        if not doctor_name:
            return jsonify({'success': False, 'message': 'Doctor name is required!'})
        if not diagnosis:
            return jsonify({'success': False, 'message': 'Diagnosis is required!'})

        # Verify UIN exists and get user_id
        user_id = None
        for uid, user in users.items():
            if user.get('uin') == uin:
                user_id = uid
                break

        if not user_id:
            return jsonify({'success': False, 'message': 'Invalid UIN!'})

        # Verify hospital exists
        if hospital_id not in hospitals:
            return jsonify({'success': False, 'message': f'Invalid hospital ID: {hospital_id}!'})

        # Create record ID
        record_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Initialize medical_records if it doesn't exist
        if 'medical_records' not in globals():
            global medical_records
            medical_records = {}

        # Create new medical record
        new_record = {
            'record_id': record_id,
            'hospital_id': hospital_id,
            'hospital_name': hospitals[hospital_id].get('name', 'Unknown Hospital'),
            'doctor_name': doctor_name,
            'diagnosis': diagnosis,
            'treatment': treatment,
            'medicines': medicines,
            'notes': notes,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add insurance information if provided
        if insurance_provider:
            new_record['insurance_provider'] = insurance_provider
        if policy_number:
            new_record['policy_number'] = policy_number
        if coverage_type:
            new_record['coverage_type'] = coverage_type
        if insurance_valid_until:
            new_record['insurance_valid_until'] = insurance_valid_until
            
        # Add follow-up information if provided
        if follow_up_date:
            new_record['follow_up_date'] = follow_up_date
        if follow_up_time:
            new_record['follow_up_time'] = follow_up_time
        if follow_up_purpose:
            new_record['follow_up_purpose'] = follow_up_purpose
            
        # Add medication details if provided
        for key, value in med_details.items():
            new_record[key] = value
            
        # Add treatment history if provided
        if treatment_history:
            new_record['treatment_history'] = treatment_history
            
        # Add certificate history if provided
        if certificate_history:
            new_record['certificate_history'] = certificate_history

        # Add the record to the UIN's records list
        if uin not in medical_records:
            medical_records[uin] = []
        
        medical_records[uin].append(new_record)

        # Save medical records to file
        save_medical_records()
        
        print(f"Added medical record for UIN: {uin}, Record ID: {record_id}")
        return jsonify({'success': True, 'message': 'Medical record added successfully'})

    except Exception as e:
        print(f"Error adding medical record: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/get_medical_history/<uin>')
def get_medical_history(uin):
    try:
        if uin not in medical_records:
            return jsonify([])
        return jsonify(medical_records[uin])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hospital_verify_uin', methods=['POST'])
def hospital_verify_uin():
    try:
        uin = request.form.get('uin', '').strip()
        
        # Find user by UIN
        user_data = None
        for user in users.values():
            if user.get('uin') == uin:
                user_data = user
                break

        if user_data:
            return jsonify({
                'verified': True,
                'user_data': {
                    'name': user_data['name'],
                    'dob': user_data['dob'],
                    'photo_path': url_for('static', filename=user_data['photo_path']) if user_data.get('photo_path') else None
                }
            })
        else:
            return jsonify({
                'verified': False,
                'message': 'Invalid UIN'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_medical_history/<unique_id>')
def download_medical_history(unique_id):
    try:
        user = users.get(unique_id)
        if not user:
            return "User not found!", 404

        # Get medical records for the user
        user_records = medical_records.get(user['uin'], [])
        
        if not user_records:
            return "No medical records found!", 404

        # Create a PDF using ReportLab
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#2c7be5')
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a1f36'),
            spaceAfter=12
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=12
        )

        # Build the PDF content
        content = []
        
        # Title
        content.append(Paragraph(f"Medical History Report", title_style))
        content.append(Paragraph(f"Patient: {user.get('first_name', '')} {user.get('last_name', '')}", heading_style))
        content.append(Paragraph(f"UIN: {user.get('uin', '')}", normal_style))
        content.append(Spacer(1, 20))

        # Add each medical record
        for record in user_records:
            # Record header
            content.append(Paragraph(f"Visit Date: {record['timestamp']}", heading_style))
            content.append(Paragraph(f"Hospital: {record['hospital_name']}", normal_style))
            content.append(Paragraph(f"Doctor: Dr. {record['doctor_name']}", normal_style))
            
            # Medical details
            content.append(Paragraph("Diagnosis:", heading_style))
            content.append(Paragraph(record['diagnosis'], normal_style))
            
            if record.get('treatment'):
                content.append(Paragraph("Treatment:", heading_style))
                content.append(Paragraph(record['treatment'], normal_style))
            
            if record.get('medicines'):
                content.append(Paragraph("Prescribed Medicines:", heading_style))
                content.append(Paragraph(record['medicines'], normal_style))
            
            if record.get('notes'):
                content.append(Paragraph("Additional Notes:", heading_style))
                content.append(Paragraph(record['notes'], normal_style))
            
            content.append(Spacer(1, 20))

        # Build the PDF
        doc.build(content)
        
        # Prepare the response
        buffer.seek(0)
        return send_file(
            BytesIO(buffer.getvalue()),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'medical_history_{unique_id}.pdf'
        )

    except Exception as e:
        print(f"Error generating medical history PDF: {str(e)}")
        return f"Error generating medical history: {str(e)}", 500

@app.route('/verify_hospital_login', methods=['POST'])
def verify_hospital_login():
    try:
        print("Form data:", request.form)
        hospital_id = request.form.get('hospital_id', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"Login attempt - Hospital ID: {hospital_id}")
        print(f"Available hospital IDs: {list(hospitals.keys())}")

        if not hospital_id or not password:
            return jsonify({
                'verified': False,
                'message': 'Hospital ID and Password are required'
            })

        # Check if hospital exists in hospitals dictionary
        hospital = hospitals.get(hospital_id)
        if not hospital:
            print(f"Hospital not found with ID: {hospital_id}")
            return jsonify({
                'verified': False,
                'message': f'Hospital not found with ID: {hospital_id}'
            })
        
        print(f"Hospital found: {hospital}")

        # Verify password
        hashed_password = hash_password(password)
        if hospital.get('password') != hashed_password:
            print("Invalid password")
            return jsonify({
                'verified': False,
                'message': 'Invalid password'
            })

        return jsonify({
            'verified': True,
            'hospital_id': hospital_id,
            'message': 'Login successful'
        })
    except Exception as e:
        print(f"Error in hospital login: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'verified': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/verify_uin', methods=['POST'])
def verify_uin():
    try:
        data = request.get_json()
        uin = data.get('uin')

        if not uin:
            return jsonify({
                'verified': False,
                'message': 'UIN is required'
            })

        # Check if user exists in users dictionary
        for user_id, user_data in users.items():
            if user_data.get('uin') == uin:
                return jsonify({
                    'verified': True,
                    'user_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}",
                    'uin': uin,
                    'user_data': {
                        'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}",
                        'dob': user_data.get('date_of_birth', ''),
                        'photo_path': user_data.get('photo_path', ''),
                        'uin': uin
                    }
                })

        return jsonify({
            'verified': False,
            'message': 'Invalid UIN. User not found.'
        })

    except Exception as e:
        return jsonify({
            'verified': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/generate-verification', methods=['GET', 'POST'])
def generate_verification():
    if request.method == 'POST':
        # Generate a random 8-digit verification ID (alphanumeric)
        verification_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Store the form data
        verification_data[verification_id] = {
            'fullName': request.form['fullName'],
            'fatherName': request.form['fatherName'],
            'dob': request.form['dob'],
            'gender': request.form['gender'],
            'bloodGroup': request.form['bloodGroup'],
            'address': request.form['address'],
            'mobile': request.form['mobile']
        }
        
        # Save to a JSON file for persistence
        with open('verification_data.json', 'w') as f:
            json.dump(verification_data, f)
        
        return render_template('generate_verification.html', verification_id=verification_id)
    
    return render_template('generate_verification.html')

@app.route('/get-verification-data/<verification_id>')
def get_verification_data(verification_id):
    try:
        # Load data from JSON file
        with open('verification_data.json', 'r') as f:
            verification_data = json.load(f)
        
        if verification_id in verification_data:
            return jsonify(verification_data[verification_id]), 200
        return jsonify({'error': 'Verification ID not found'}), 404
    except:
        return jsonify({'error': 'Error retrieving data'}), 500

@app.route('/view_certificate/<record_id>')
def view_certificate(record_id):
    try:
        # Get the medical record from the global variable
        record = None
        user = None
        user_records = []
        user_unique_id = None
        
        # Find the record and associated user
        for uin, records in medical_records.items():
            for r in records:
                if r.get('record_id') == record_id:
                    record = r
                    user_records = records
                    # Get user data from the global variable
                    for unique_id, user_data in users.items():
                        if user_data.get('uin') == uin:
                            user = user_data.copy()  # Create a copy to avoid modifying the original
                            # Add unique_id to user data for QR code
                            user['unique_id'] = unique_id
                            user_unique_id = unique_id
                            
                            # Map fields to match template expectations
                            if 'first_name' in user and 'last_name' in user:
                                user['name'] = f"{user['first_name']} {user['last_name']}".strip()
                            elif 'first_name' in user:
                                user['name'] = user['first_name']
                            
                            if 'date_of_birth' in user and 'dob' not in user:
                                user['dob'] = user['date_of_birth']
                            
                            break
                    break
            if record:
                break
        
        if not record or not user:
            return "Record not found", 404
            
        # Get hospital data from the global variable
        hospital = None
        for hospital_id, hospital_data in hospitals.items():
            if hospital_id == record.get('hospital_id'):
                hospital = hospital_data
                break
                
        # Add hospital name to record for display
        record['hospital_name'] = hospital.get('name') if hospital else 'Unknown Hospital'
        
        # Ensure all necessary fields are available
        if 'name' not in user:
            user['name'] = 'Unknown Patient'
        if 'dob' not in user:
            user['dob'] = 'Not Available'
        if 'address' not in user:
            user['address'] = 'Not Available'
        if 'phone' not in user:
            user['phone'] = 'Not Available'
        
        # Set photo path if available
        if 'photo_path' not in user and user.get('unique_id'):
            possible_photo_path = f"user_photos/{user['unique_id']}.jpg"
            if os.path.exists(os.path.join('static', possible_photo_path)):
                user['photo_path'] = possible_photo_path
        
        # Add insurance information if not present
        if 'insurance_provider' not in user:
            user['insurance_provider'] = record.get('insurance_provider', 'Not Available')
        if 'policy_number' not in user:
            user['policy_number'] = record.get('policy_number', 'Not Available')
        if 'coverage_type' not in user:
            user['coverage_type'] = record.get('coverage_type', 'Not Available')
        if 'insurance_valid_until' not in user:
            user['insurance_valid_until'] = record.get('insurance_valid_until', 'Not Available')
        
        # Create medication schedule
        medications = []
        if record.get('medicines'):
            # Parse medicines from the record
            medicine_list = record.get('medicines', '').split('\n')
            for i, med in enumerate(medicine_list):
                if med.strip():
                    # Create a medication object with default values
                    medication = {
                        'name': med.strip(),
                        'dosage': record.get(f'med_{i}_dosage', 'As directed'),
                        'frequency': record.get(f'med_{i}_frequency', 'As needed'),
                        'duration': record.get(f'med_{i}_duration', 'Until symptoms resolve'),
                        'instructions': record.get(f'med_{i}_instructions', '')
                    }
                    medications.append(medication)
        
        # Create follow-up appointments
        appointments = []
        if record.get('follow_up_date'):
            appointment = {
                'date': record.get('follow_up_date', ''),
                'time': record.get('follow_up_time', ''),
                'doctor': f"Dr. {record.get('doctor_name', '')}",
                'purpose': record.get('follow_up_purpose', 'Follow-up consultation'),
                'location': record.get('hospital_name', '')
            }
            appointments.append(appointment)
        
        # Create treatment history from previous records
        treatment_history = []
        for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
            if r.get('record_id') != record_id:  # Exclude current record
                treatment = {
                    'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                    'title': r.get('diagnosis', 'Medical Visit'),
                    'description': f"Treatment: {r.get('treatment', 'Not specified')}"
                }
                treatment_history.append(treatment)
                if len(treatment_history) >= 5:  # Limit to 5 previous treatments
                    break
        
        # Create certificate history from previous records
        certificate_history = []
        for r in sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True):
            if r.get('record_id') != record_id:  # Exclude current record
                cert = {
                    'date': r.get('timestamp', '').split(' ')[0] if ' ' in r.get('timestamp', '') else r.get('timestamp', ''),
                    'type': 'Medical Certificate',
                    'doctor': f"Dr. {r.get('doctor_name', '')}",
                    'purpose': r.get('diagnosis', 'Medical Documentation'),
                    'link': url_for('generate_certificate', record_id=r.get('record_id'), unique_id=user_unique_id)
                }
                certificate_history.append(cert)
                if len(certificate_history) >= 3:  # Limit to 3 previous certificates
                    break
        
        # Render the certificate template
        return render_template('medical_certificate.html', 
                              record=record, 
                              user=user,
                              medications=medications,
                              appointments=appointments,
                              treatment_history=treatment_history,
                              certificate_history=certificate_history)
        
    except Exception as e:
        print(f"Error viewing certificate: {str(e)}")
        return "Error viewing certificate", 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
