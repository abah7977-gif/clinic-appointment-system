from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, date, time, timedelta
from functools import wraps
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
database_url = os.getenv('DATABASE_URL', 'sqlite:///clinic_v3.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://') and '+psycopg' not in database_url:
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    room = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True, nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    doctor = db.relationship('Doctor')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class DoctorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    doctor = db.relationship('Doctor', backref='schedules')

class DoctorLeave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    leave_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    doctor = db.relationship('Doctor', backref='leave_records')

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_no = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30, nullable=False)
    queue_number = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(40), default='Scheduled', nullable=False)
    check_in_time = db.Column(db.DateTime)
    called_time = db.Column(db.DateTime)
    consultation_start = db.Column(db.DateTime)
    consultation_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated: return login_manager.unauthorized()
            if current_user.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def dt_for(d,t): return datetime.combine(d,t)
def minutes_between(a,b): return None if not a or not b else max(0, round((b-a).total_seconds()/60,1))

def doctor_is_scheduled(doctor_id, appt_date, start_t, duration):
    start_dt = dt_for(appt_date,start_t); end_dt = start_dt + timedelta(minutes=duration)
    for s in DoctorSchedule.query.filter_by(doctor_id=doctor_id, weekday=appt_date.weekday()).all():
        if start_dt >= dt_for(appt_date,s.start_time) and end_dt <= dt_for(appt_date,s.end_time): return True
    return False

def doctor_on_leave(doctor_id, appt_date):
    return DoctorLeave.query.filter_by(doctor_id=doctor_id, leave_date=appt_date).first() is not None

def appointment_overlaps(doctor_id, appt_date, start_t, duration, exclude_id=None):
    start_dt = dt_for(appt_date,start_t); end_dt = start_dt + timedelta(minutes=duration)
    q = Appointment.query.filter(Appointment.doctor_id==doctor_id, Appointment.appointment_date==appt_date, Appointment.status.notin_(['Cancelled','No Show']))
    if exclude_id: q = q.filter(Appointment.id != exclude_id)
    for a in q.all():
        a_start = dt_for(a.appointment_date,a.scheduled_time); a_end = a_start + timedelta(minutes=a.duration_minutes)
        if start_dt < a_end and end_dt > a_start: return True
    return False

def available_doctors(appt_date,start_t,duration,exclude_id=None):
    result=[]
    for d in Doctor.query.filter_by(active=True).order_by(Doctor.name).all():
        if not doctor_is_scheduled(d.id,appt_date,start_t,duration): continue
        if doctor_on_leave(d.id,appt_date): continue
        if appointment_overlaps(d.id,appt_date,start_t,duration,exclude_id): continue
        workload = Appointment.query.filter(Appointment.doctor_id==d.id, Appointment.appointment_date==appt_date, Appointment.status.notin_(['Cancelled','No Show'])).count()
        result.append((d,workload))
    return sorted(result,key=lambda x:(x[1],x[0].name))

def next_queue_number(appt_date):
    count = Appointment.query.filter(Appointment.appointment_date==appt_date, Appointment.status!='Cancelled').count()
    return f'A{count+1:03d}'

@app.context_processor
def inject_globals(): return {'current_date':date.today()}

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method=='POST':
        u=User.query.filter_by(username=request.form['username'].strip()).first()
        if u and u.check_password(request.form['password']): login_user(u); return redirect(url_for('dashboard'))
        flash('Invalid username or password.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    today=date.today(); q=Appointment.query.filter_by(appointment_date=today)
    if current_user.role=='Doctor' and current_user.doctor_id: q=q.filter_by(doctor_id=current_user.doctor_id)
    rows=q.order_by(Appointment.scheduled_time).all(); waits=[]; consults=[]
    for a in rows:
        if a.consultation_start: waits.append(minutes_between(dt_for(a.appointment_date,a.scheduled_time),a.consultation_start))
        if a.consultation_start and a.consultation_end: consults.append(minutes_between(a.consultation_start,a.consultation_end))
    stats={'total':len(rows),'waiting':sum(a.status in ['Checked In','Called'] for a in rows),'in_consultation':sum(a.status=='In Consultation' for a in rows),'completed':sum(a.status=='Completed' for a in rows),'no_show':sum(a.status=='No Show' for a in rows),'avg_wait':round(sum(waits)/len(waits),1) if waits else 0,'avg_consult':round(sum(consults)/len(consults),1) if consults else 0}
    doctor_counts=[]
    for d in Doctor.query.filter_by(active=True).order_by(Doctor.name).all():
        if current_user.role=='Doctor' and current_user.doctor_id!=d.id: continue
        doctor_counts.append((d.name,Appointment.query.filter_by(appointment_date=today,doctor_id=d.id).count()))
    statuses=['Scheduled','Checked In','Called','In Consultation','Completed','No Show','Cancelled']
    return render_template('dashboard.html',appointments=rows,stats=stats,doctor_labels=[x[0] for x in doctor_counts],doctor_values=[x[1] for x in doctor_counts],status_labels=statuses,status_values=[sum(a.status==s for a in rows) for s in statuses])

@app.route('/patients')
@login_required
def patients():
    search=request.args.get('q','').strip(); q=Patient.query
    if search:
        like=f'%{search}%'; q=q.filter(db.or_(Patient.patient_no.ilike(like),Patient.name.ilike(like),Patient.phone.ilike(like)))
    return render_template('patients.html',patients=q.order_by(Patient.name).all(),search=search)

@app.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    p=db.get_or_404(Patient,patient_id); apps=Appointment.query.filter_by(patient_id=p.id).order_by(Appointment.appointment_date.desc(),Appointment.scheduled_time.desc()).all()
    return render_template('patient_detail.html',patient=p,appointments=apps)

@app.route('/appointments')
@login_required
def appointments():
    q=Appointment.query
    if current_user.role=='Doctor' and current_user.doctor_id: q=q.filter_by(doctor_id=current_user.doctor_id)
    return render_template('appointments.html',appointments=q.order_by(Appointment.appointment_date.desc(),Appointment.scheduled_time.desc()).all())

@app.route('/appointment/new',methods=['GET','POST'])
@role_required('Admin','Receptionist')
def new_appointment():
    doctors=Doctor.query.filter_by(active=True).order_by(Doctor.name).all()
    if request.method=='POST':
        pno=request.form['patient_no'].strip(); pname=request.form['patient_name'].strip(); phone=request.form.get('phone','').strip()
        adate=datetime.strptime(request.form['appointment_date'],'%Y-%m-%d').date(); atime=datetime.strptime(request.form['scheduled_time'],'%H:%M').time(); duration=int(request.form['duration_minutes']); requested=request.form.get('doctor_id','').strip()
        p=Patient.query.filter_by(patient_no=pno).first()
        if not p: p=Patient(patient_no=pno,name=pname,phone=phone); db.session.add(p); db.session.flush()
        else: p.name=pname; p.phone=phone
        avail=available_doctors(adate,atime,duration); ids=[str(x[0].id) for x in avail]
        if requested and requested not in ids: flash('Selected doctor is not available for this time slot.','danger'); return redirect(url_for('new_appointment'))
        if not requested and not avail: flash('No doctor is available for this time slot.','danger'); return redirect(url_for('new_appointment'))
        did=int(requested) if requested else avail[0][0].id
        a=Appointment(patient_id=p.id,doctor_id=did,appointment_date=adate,scheduled_time=atime,duration_minutes=duration,queue_number=next_queue_number(adate),status='Scheduled')
        db.session.add(a); db.session.commit(); flash(f'Appointment created. Queue number: {a.queue_number}','success'); return redirect(url_for('appointments'))
    return render_template('appointment_form.html',doctors=doctors,appointment=None)

@app.route('/appointment/<int:appointment_id>/reschedule',methods=['GET','POST'])
@role_required('Admin','Receptionist')
def reschedule_appointment(appointment_id):
    a=db.get_or_404(Appointment,appointment_id); doctors=Doctor.query.filter_by(active=True).order_by(Doctor.name).all()
    if request.method=='POST':
        adate=datetime.strptime(request.form['appointment_date'],'%Y-%m-%d').date(); atime=datetime.strptime(request.form['scheduled_time'],'%H:%M').time(); duration=int(request.form['duration_minutes']); requested=request.form.get('doctor_id','').strip()
        avail=available_doctors(adate,atime,duration,exclude_id=a.id); ids=[str(x[0].id) for x in avail]
        if requested and requested not in ids: flash('Selected doctor is not available for this time slot.','danger'); return redirect(url_for('reschedule_appointment',appointment_id=a.id))
        if not requested and not avail: flash('No doctor is available for this time slot.','danger'); return redirect(url_for('reschedule_appointment',appointment_id=a.id))
        a.doctor_id=int(requested) if requested else avail[0][0].id; a.appointment_date=adate; a.scheduled_time=atime; a.duration_minutes=duration; a.status='Scheduled'; a.check_in_time=a.called_time=a.consultation_start=a.consultation_end=None
        db.session.commit(); flash('Appointment rescheduled successfully.','success'); return redirect(url_for('appointments'))
    return render_template('appointment_form.html',doctors=doctors,appointment=a)

@app.post('/appointment/<int:appointment_id>/action')
@login_required
def appointment_action(appointment_id):
    a=db.get_or_404(Appointment,appointment_id)
    if current_user.role=='Doctor' and current_user.doctor_id!=a.doctor_id: abort(403)
    action=request.form['action']; now=datetime.now()
    if action=='checkin' and current_user.role in ['Admin','Receptionist']: a.check_in_time=now; a.status='Checked In'
    elif action=='call' and current_user.role in ['Admin','Receptionist','Doctor']: a.called_time=now; a.status='Called'
    elif action=='start' and current_user.role in ['Admin','Doctor']: a.consultation_start=now; a.status='In Consultation'
    elif action=='complete' and current_user.role in ['Admin','Doctor']: a.consultation_end=now; a.status='Completed'
    elif action=='noshow' and current_user.role in ['Admin','Receptionist']: a.status='No Show'
    elif action=='cancel' and current_user.role in ['Admin','Receptionist']: a.status='Cancelled'
    else: abort(403)
    db.session.commit(); return redirect(request.referrer or url_for('appointments'))

@app.route('/queue')
@login_required
def queue_board():
    q=Appointment.query.filter(Appointment.appointment_date==date.today(),Appointment.status.in_(['Checked In','Called','In Consultation']))
    if current_user.role=='Doctor' and current_user.doctor_id: q=q.filter_by(doctor_id=current_user.doctor_id)
    return render_template('queue.html',appointments=q.order_by(Appointment.scheduled_time).all())

@app.route('/doctors')
@role_required('Admin')
def doctors(): return render_template('doctors.html',doctors=Doctor.query.order_by(Doctor.name).all())

@app.post('/doctor/add')
@role_required('Admin')
def add_doctor():
    name=request.form['name'].strip(); room=request.form.get('room','').strip()
    if name: db.session.add(Doctor(name=name,room=room,active=True)); db.session.commit()
    return redirect(url_for('doctors'))

@app.post('/doctor/<int:doctor_id>/toggle')
@role_required('Admin')
def toggle_doctor(doctor_id):
    d=db.get_or_404(Doctor,doctor_id); d.active=not d.active; db.session.commit(); return redirect(url_for('doctors'))

@app.route('/doctor/<int:doctor_id>/schedule',methods=['GET','POST'])
@role_required('Admin')
def doctor_schedule(doctor_id):
    d=db.get_or_404(Doctor,doctor_id)
    if request.method=='POST':
        db.session.add(DoctorSchedule(doctor_id=d.id,weekday=int(request.form['weekday']),start_time=datetime.strptime(request.form['start_time'],'%H:%M').time(),end_time=datetime.strptime(request.form['end_time'],'%H:%M').time())); db.session.commit(); return redirect(url_for('doctor_schedule',doctor_id=d.id))
    return render_template('doctor_schedule.html',doctor=d,schedules=DoctorSchedule.query.filter_by(doctor_id=d.id).order_by(DoctorSchedule.weekday).all())

@app.post('/schedule/<int:schedule_id>/delete')
@role_required('Admin')
def delete_schedule(schedule_id):
    s=db.get_or_404(DoctorSchedule,schedule_id); did=s.doctor_id; db.session.delete(s); db.session.commit(); return redirect(url_for('doctor_schedule',doctor_id=did))

@app.route('/doctor/<int:doctor_id>/leave',methods=['GET','POST'])
@role_required('Admin')
def doctor_leave(doctor_id):
    d=db.get_or_404(Doctor,doctor_id)
    if request.method=='POST':
        db.session.add(DoctorLeave(doctor_id=d.id,leave_date=datetime.strptime(request.form['leave_date'],'%Y-%m-%d').date(),reason=request.form.get('reason','').strip())); db.session.commit(); return redirect(url_for('doctor_leave',doctor_id=d.id))
    return render_template('doctor_leave.html',doctor=d,leaves=DoctorLeave.query.filter_by(doctor_id=d.id).order_by(DoctorLeave.leave_date.desc()).all())

@app.post('/leave/<int:leave_id>/delete')
@role_required('Admin')
def delete_leave(leave_id):
    l=db.get_or_404(DoctorLeave,leave_id); did=l.doctor_id; db.session.delete(l); db.session.commit(); return redirect(url_for('doctor_leave',doctor_id=did))

@app.route('/availability')
@role_required('Admin','Receptionist')
def availability():
    ds=request.args.get('date',''); ts=request.args.get('time',''); duration=int(request.args.get('duration',30)); avail=[]
    if ds and ts: avail=available_doctors(datetime.strptime(ds,'%Y-%m-%d').date(),datetime.strptime(ts,'%H:%M').time(),duration)
    return render_template('availability.html',date_str=ds,time_str=ts,duration=duration,available=avail)

def seed():
    db.create_all()
    if Doctor.query.count()==0:
        docs=[Doctor(name='Dr. Adam Lee',room='Room 1'),Doctor(name='Dr. Sarah Lim',room='Room 2'),Doctor(name='Dr. Daniel Wong',room='Room 3')]; db.session.add_all(docs); db.session.flush()
        for d in docs:
            for wd in range(5): db.session.add(DoctorSchedule(doctor_id=d.id,weekday=wd,start_time=time(8,0),end_time=time(17,0)))
    if User.query.count()==0:
        admin=User(username='admin',role='Admin'); admin.set_password('admin123')
        rec=User(username='receptionist',role='Receptionist'); rec.set_password('reception123')
        first=Doctor.query.order_by(Doctor.id).first(); doc=User(username='doctor1',role='Doctor',doctor_id=first.id); doc.set_password('doctor123')
        db.session.add_all([admin,rec,doc])
    db.session.commit()

with app.app_context(): seed()
if __name__=='__main__': app.run(debug=True)
