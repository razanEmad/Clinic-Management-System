from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

# Set folders to 'public' as per your original structure
app = Flask(__name__, static_folder='public', template_folder='public', static_url_path='')
app.secret_key = "clinic_secret_key"

# --- Database Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='patient') # 'patient' or 'doctor'
    gender = db.Column(db.String(20), default='Not Specified')
    age = db.Column(db.String(10), default='N/A')
    address = db.Column(db.String(200), default='N/A')
    phone = db.Column(db.String(20), default='N/A')
    # Link to medical history
    history = db.relationship('MedicalHistory', backref='patient', lazy=True)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    img = db.Column(db.String(100), nullable=False)
    dept = db.Column(db.String(50), nullable=False)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)

class MedicalHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- Context Processor ---
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(user=user)

# --- Routes ---

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conpassword = request.form.get('conpassword')

        if password != conpassword:
            flash("Passwords do not match!", "error")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "error")
            return redirect(url_for('register'))
        
        new_user = User(
            fullname=request.form.get('fullname'),
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()
        
        # Add initial history record
        initial_history = MedicalHistory(record="New Patient Registered", user_id=new_user.id)
        db.session.add(initial_history)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.password == password:

            session['user_id'] = user.id
            flash(f"Welcome back, {user.fullname}!", "success")
            if user.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('home'))
        else:
            flash("Invalid Email or Password.", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.gender = request.form.get('gender')
        user.age = request.form.get('age')
        user.address = request.form.get('address')
        user.phone = request.form.get('phone')
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))
        
    return render_template('edit_profile.html', patient=user)

@app.route('/add-history/<email>', methods=['POST'])
def add_history(email):
    if 'user_id' not in session: return redirect(url_for('login'))
    current_user = User.query.get(session['user_id'])
    if current_user.role != 'doctor': return redirect(url_for('home'))
    
    target_patient = User.query.filter_by(email=email).first()
    new_record_text = request.form.get('new_record')
    
    if target_patient and new_record_text:
        timestamp = datetime.now().strftime("%b %d, %Y")
        new_entry = MedicalHistory(record=f"{timestamp}: {new_record_text}", user_id=target_patient.id)
        db.session.add(new_entry)
        db.session.commit()
        flash("Medical record added!", "success")
    return redirect(url_for('patient_history', email=email))

@app.route('/doctors')
def doctors():
    doctors_list = Doctor.query.all()
    return render_template('doctors.html', doctors_list=doctors_list)

@app.route('/doctor/<int:doc_id>')
def doctor_profile(doc_id):
    doctor = Doctor.query.get_or_404(doc_id)
    return render_template('doctor-profile.html', doctor=doctor, doc_id=doc_id)

@app.route('/book', methods=['POST'])
def book():
    if 'user_id' not in session:
        flash("Please log in to book an appointment.", "error")
        return redirect(url_for('login'))
    
    doc_id = request.form.get('doc_id')
    date_str = request.form.get('date')
    time = request.form.get('time')

    if datetime.strptime(date_str, '%Y-%m-%d').date() < datetime.now().date():
        flash("Error: Cannot book a date in the past!", "error")
        return redirect(url_for('doctor_profile', doc_id=doc_id))

    existing_appt = Appointment.query.filter_by(
        doctor_id=doc_id,
        date=date_str,
        time=time
    ).first()

    if existing_appt:
        flash("This date and time is already reserved.", "error")
        return redirect(url_for('doctor_profile', doc_id=doc_id))
    
    new_appt = Appointment(date=date_str, time=time, user_id=session['user_id'], doctor_id=doc_id)
    db.session.add(new_appt)
    db.session.commit()

    flash("Appointment Booked Successfully!", "success")
    return redirect(url_for('my_appointments'))

@app.route('/my-appointments')
def my_appointments():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('appointments.html', appointments=user.appointments)

@app.route('/cancel/<int:app_id>')
def cancel_appointment(app_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    appt = Appointment.query.get_or_404(app_id)
    if appt.user_id == session['user_id']:
        db.session.delete(appt)
        db.session.commit()
        flash("Appointment cancelled.", "success")
    return redirect(url_for('my_appointments'))

@app.route('/doctor-dashboard')
def doctor_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user.role != 'doctor': return redirect(url_for('home'))
    
    # In a real app, doctors would have their own ID in the Doctor table.
    # Here we assume the Doctor ID matches the User ID or we search by name.
    doctor = Doctor.query.filter_by(name=user.fullname).first()
    appts = doctor.appointments if doctor else []
    
    return render_template('doctor-dashboard.html', appointments=appts)

@app.route('/patient-history/<email>')
def patient_history(email):
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user.role != 'doctor': return redirect(url_for('home'))
    
    patient_data = User.query.filter_by(email=email).first()
    return render_template('patient_profile.html', patient=patient_data, view_only=True)

@app.route('/profile')
def profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('patient_profile.html', patient=user, view_only=False)

# --- Initialization (Create DB and Seed Data) ---

def init_db():
    with app.app_context():
        db.create_all()

        # List of doctors to seed
        doctors_list = [
            {"email": "doc1@clinic.com", "fullname": "Dr. Jessica Brown", "specialty": "Dentist", "img": "doctor1.jpg", "dept": "dental"},
            {"email": "doc2@clinic.com", "fullname": "Dr. Brain Adam", "specialty": "Cardiologist", "img": "doctor2.jpg", "dept": "cardiology"},
            {"email": "doc3@clinic.com", "fullname": "Dr. Ahmed Adam", "specialty": "Neurologist", "img": "doctor3.jpg", "dept": "neurology"},
            {"email": "doc4@clinic.com", "fullname": "Dr. Aya Brown", "specialty": "Pediatrician", "img": "doctor4.jpg", "dept": "pediatric"},
        ]

        for doc in doctors_list:
            # Check if doctor exists in User table
            if not User.query.filter_by(email=doc["email"]).first():
                new_user = User(
                    email=doc["email"],
                    password="123",  # plaintext, remove hashing if you want
                    fullname=doc["fullname"],
                    role="doctor"
                )
                db.session.add(new_user)

            # Check if doctor exists in Doctor table
            if not Doctor.query.filter_by(name=doc["fullname"]).first():
                new_doc = Doctor(
                    name=doc["fullname"],
                    specialty=doc["specialty"],
                    img=doc["img"],
                    dept=doc["dept"]
                )
                db.session.add(new_doc)

        db.session.commit()
        print("Database created and seeded with doctors!")





if __name__ == '__main__':
    init_db()
    app.run(debug=True)


