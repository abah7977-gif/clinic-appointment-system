from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from dotenv import load_dotenv

from datetime import (
    datetime,
    date,
    time,
    timedelta
)

from zoneinfo import ZoneInfo

from sqlalchemy import (
    text,
    inspect
)

from functools import wraps

import os


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

load_dotenv()

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")


def malaysia_now():
    return datetime.now(MALAYSIA_TZ).replace(tzinfo=None)


def malaysia_today():
    return malaysia_now().date()


app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///clinic_v3.db"
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif (
    database_url.startswith("postgresql://")
    and "+psycopg" not in database_url
):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )


app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# =========================================================
# DATABASE MODELS
# =========================================================

class Doctor(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    room = db.Column(
        db.String(50),
        nullable=True
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    archived = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )


class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctor.id"),
        nullable=True
    )

    enabled = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    doctor = db.relationship(
        "Doctor",
        foreign_keys=[doctor_id]
    )

    def set_password(self, password):

        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):

        return check_password_hash(
            self.password_hash,
            password
        )

    @property
    def is_active(self):

        return bool(self.enabled)


class DoctorSchedule(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctor.id"),
        nullable=False
    )

    weekday = db.Column(
        db.Integer,
        nullable=False
    )

    start_time = db.Column(
        db.Time,
        nullable=False
    )

    end_time = db.Column(
        db.Time,
        nullable=False
    )

    doctor = db.relationship(
        "Doctor",
        backref="schedules"
    )


class DoctorLeave(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctor.id"),
        nullable=False
    )

    leave_date = db.Column(
        db.Date,
        nullable=False
    )

    reason = db.Column(
        db.String(200),
        nullable=True
    )

    doctor = db.relationship(
        "Doctor",
        backref="leave_records"
    )


class Patient(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    patient_no = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    phone = db.Column(
        db.String(50),
        nullable=True
    )

    archived = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )


class Appointment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patient.id"),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctor.id"),
        nullable=False
    )

    appointment_date = db.Column(
        db.Date,
        nullable=False
    )

    scheduled_time = db.Column(
        db.Time,
        nullable=False
    )

    duration_minutes = db.Column(
        db.Integer,
        default=30,
        nullable=False
    )

    queue_number = db.Column(
        db.String(30),
        nullable=False
    )

    status = db.Column(
        db.String(40),
        default="Scheduled",
        nullable=False
    )

    check_in_time = db.Column(
        db.DateTime,
        nullable=True
    )

    called_time = db.Column(
        db.DateTime,
        nullable=True
    )

    consultation_start = db.Column(
        db.DateTime,
        nullable=True
    )

    consultation_end = db.Column(
        db.DateTime,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=malaysia_now,
        nullable=False
    )

    patient = db.relationship(
        "Patient",
        backref="appointments"
    )

    doctor = db.relationship(
        "Doctor",
        backref="appointments"
    )


class SystemSetting(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    default_slot_minutes = db.Column(
        db.Integer,
        default=30,
        nullable=False
    )


class DateSlotSetting(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    setting_date = db.Column(
        db.Date,
        unique=True,
        nullable=False
    )

    slot_minutes = db.Column(
        db.Integer,
        nullable=False
    )


class BlockedSlot(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    block_date = db.Column(
        db.Date,
        nullable=False
    )

    block_time = db.Column(
        db.Time,
        nullable=False
    )

    reason = db.Column(
        db.String(200),
        nullable=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "block_date",
            "block_time",
            name="uq_blocked_slot"
        ),
    )


# =========================================================
# LOGIN
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    return db.session.get(
        User,
        int(user_id)
    )


def role_required(*roles):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if not current_user.is_authenticated:
                return login_manager.unauthorized()

            if current_user.role not in roles:
                abort(403)

            return function(*args, **kwargs)

        return wrapper

    return decorator


# =========================================================
# GENERAL HELPERS
# =========================================================

def dt_for(
    appointment_date,
    appointment_time
):

    return datetime.combine(
        appointment_date,
        appointment_time
    )


def minutes_between(
    start_dt,
    end_dt
):

    if not start_dt or not end_dt:
        return None

    return max(
        0,
        round(
            (
                end_dt - start_dt
            ).total_seconds() / 60,
            1
        )
    )


def get_system_setting():

    setting = SystemSetting.query.first()

    if not setting:

        setting = SystemSetting(
            default_slot_minutes=30
        )

        db.session.add(setting)
        db.session.commit()

    return setting


def get_slot_duration(
    selected_date
):

    override = DateSlotSetting.query.filter_by(
        setting_date=selected_date
    ).first()

    if override:
        return override.slot_minutes

    return get_system_setting().default_slot_minutes


def doctor_on_leave(
    doctor_id,
    selected_date
):

    return (
        DoctorLeave.query.filter_by(
            doctor_id=doctor_id,
            leave_date=selected_date
        ).first()
        is not None
    )


def doctor_is_scheduled(
    doctor_id,
    selected_date,
    slot_time,
    duration
):

    weekday = selected_date.weekday()

    schedules = DoctorSchedule.query.filter_by(
        doctor_id=doctor_id,
        weekday=weekday
    ).all()

    if not schedules:
        return False

    appointment_start = datetime.combine(
        selected_date,
        slot_time
    )

    appointment_end = (
        appointment_start
        + timedelta(minutes=duration)
    )

    for schedule in schedules:

        schedule_start = datetime.combine(
            selected_date,
            schedule.start_time
        )

        schedule_end = datetime.combine(
            selected_date,
            schedule.end_time
        )

        if (
            appointment_start >= schedule_start
            and
            appointment_end <= schedule_end
        ):
            return True

    return False


def appointment_overlaps(
    doctor_id,
    selected_date,
    slot_time,
    duration,
    exclude_id=None
):

    new_start = datetime.combine(
        selected_date,
        slot_time
    )

    new_end = (
        new_start
        + timedelta(minutes=duration)
    )

    query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == selected_date,
        Appointment.status.notin_(
            [
                "Cancelled",
                "No Show"
            ]
        )
    )

    if exclude_id:

        query = query.filter(
            Appointment.id != exclude_id
        )

    for appointment in query.all():

        existing_start = datetime.combine(
            appointment.appointment_date,
            appointment.scheduled_time
        )

        existing_end = (
            existing_start
            + timedelta(
                minutes=appointment.duration_minutes
            )
        )

        if (
            new_start < existing_end
            and
            new_end > existing_start
        ):
            return True

    return False


def slot_is_blocked(
    selected_date,
    slot_time
):

    return (
        BlockedSlot.query.filter_by(
            block_date=selected_date,
            block_time=slot_time
        ).first()
        is not None
    )


def available_doctors(
    selected_date,
    slot_time,
    duration,
    exclude_id=None
):

    if slot_is_blocked(
        selected_date,
        slot_time
    ):
        return []

    result = []

    doctors = Doctor.query.filter_by(
        active=True,
        archived=False
    ).order_by(
        Doctor.name
    ).all()

    for doctor in doctors:

        if doctor_on_leave(
            doctor.id,
            selected_date
        ):
            continue

        if not doctor_is_scheduled(
            doctor.id,
            selected_date,
            slot_time,
            duration
        ):
            continue

        if appointment_overlaps(
            doctor.id,
            selected_date,
            slot_time,
            duration,
            exclude_id
        ):
            continue

        daily_workload = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == selected_date,
            Appointment.status.notin_(
                [
                    "Cancelled",
                    "No Show"
                ]
            )
        ).count()

        result.append(
            (
                doctor,
                daily_workload
            )
        )

    result.sort(
        key=lambda item: (
            item[1],
            item[0].name
        )
    )

    return result


def get_clinic_time_range(
    selected_date
):

    weekday = selected_date.weekday()

    schedules = (
        DoctorSchedule.query
        .join(Doctor)
        .filter(
            DoctorSchedule.weekday == weekday,
            Doctor.active.is_(True),
            Doctor.archived.is_(False)
        )
        .all()
    )

    if not schedules:
        return None, None

    earliest = min(
        schedule.start_time
        for schedule in schedules
    )

    latest = max(
        schedule.end_time
        for schedule in schedules
    )

    return earliest, latest


def generate_slots(
    selected_date
):

    duration = get_slot_duration(
        selected_date
    )

    start_time_value, end_time_value = (
        get_clinic_time_range(
            selected_date
        )
    )

    if (
        not start_time_value
        or
        not end_time_value
    ):
        return []

    current_slot = datetime.combine(
        selected_date,
        start_time_value
    )

    clinic_end = datetime.combine(
        selected_date,
        end_time_value
    )

    slots = []

    while (
        current_slot
        + timedelta(minutes=duration)
        <= clinic_end
    ):

        slot_time = current_slot.time()

        blocked = slot_is_blocked(
            selected_date,
            slot_time
        )

        available = available_doctors(
            selected_date,
            slot_time,
            duration
        )

        if blocked:

            status = "BLOCKED"

        elif len(available) == 0:

            status = "FULL"

        else:

            status = "AVAILABLE"

        slots.append(
            {
                "time": slot_time,
                "time_text": slot_time.strftime(
                    "%H:%M"
                ),
                "duration": duration,
                "available_count": len(
                    available
                ),
                "available_doctors": [
                    doctor
                    for doctor, workload
                    in available
                ],
                "status": status
            }
        )

        current_slot = (
            current_slot
            + timedelta(minutes=duration)
        )

    return slots


def next_queue_number(
    selected_date
):

    count = Appointment.query.filter(
        Appointment.appointment_date
        == selected_date,
        Appointment.status
        != "Cancelled"
    ).count()

    return f"A{count + 1:03d}"


# =========================================================
# AUTHENTICATION
# =========================================================

@app.route(
    "/login",
    methods=[
        "GET",
        "POST"
    ]
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        user = User.query.filter_by(
            username=username
        ).first()

        if (
            user
            and
            user.enabled
            and
            user.check_password(password)
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid username, password or inactive account.",
            "danger"
        )

    return render_template(
        "login.html"
    )


@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.context_processor
def inject_globals():

    return {
        "current_date": malaysia_today()
    }


@app.route("/")
@login_required
def dashboard():

    today = malaysia_today()

    query = Appointment.query.filter_by(
        appointment_date=today
    )

    if (
        current_user.role == "Doctor"
        and
        current_user.doctor_id
    ):

        query = query.filter_by(
            doctor_id=current_user.doctor_id
        )

    rows = query.order_by(
        Appointment.scheduled_time
    ).all()

    waiting_times = []
    consultation_times = []

    for appointment in rows:

        scheduled_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.scheduled_time
        )

        if appointment.consultation_start:

            waiting_times.append(
                minutes_between(
                    scheduled_datetime,
                    appointment.consultation_start
                )
            )

        if (
            appointment.consultation_start
            and
            appointment.consultation_end
        ):

            consultation_times.append(
                minutes_between(
                    appointment.consultation_start,
                    appointment.consultation_end
                )
            )

    stats = {

        "total": len(rows),

        "waiting": sum(
            1
            for appointment in rows
            if appointment.status
            in [
                "Checked In",
                "Called"
            ]
        ),

        "in_consultation": sum(
            1
            for appointment in rows
            if appointment.status
            == "In Consultation"
        ),

        "completed": sum(
            1
            for appointment in rows
            if appointment.status
            == "Completed"
        ),

        "no_show": sum(
            1
            for appointment in rows
            if appointment.status
            == "No Show"
        ),

        "avg_wait": (
            round(
                sum(waiting_times)
                /
                len(waiting_times),
                1
            )
            if waiting_times
            else 0
        ),

        "avg_consult": (
            round(
                sum(consultation_times)
                /
                len(consultation_times),
                1
            )
            if consultation_times
            else 0
        )
    }

    doctor_counts = []

    doctors = Doctor.query.filter_by(
        active=True,
        archived=False
    ).order_by(
        Doctor.name
    ).all()

    for doctor in doctors:

        if (
            current_user.role
            == "Doctor"
            and
            current_user.doctor_id
            != doctor.id
        ):
            continue

        count = Appointment.query.filter_by(
            appointment_date=today,
            doctor_id=doctor.id
        ).count()

        doctor_counts.append(
            (
                doctor.name,
                count
            )
        )

    status_names = [
        "Scheduled",
        "Checked In",
        "Called",
        "In Consultation",
        "Completed",
        "No Show",
        "Cancelled"
    ]

    status_counts = [
        sum(
            1
            for appointment in rows
            if appointment.status == status
        )
        for status in status_names
    ]

    return render_template(
        "dashboard.html",
        appointments=rows,
        stats=stats,
        doctor_labels=[
            item[0]
            for item in doctor_counts
        ],
        doctor_values=[
            item[1]
            for item in doctor_counts
        ],
        status_labels=status_names,
        status_values=status_counts
    )


# =========================================================
# PATIENT MANAGEMENT
# =========================================================

@app.route("/patients")
@login_required
def patients():

    search = request.args.get(
        "q",
        ""
    ).strip()

    query = Patient.query

    if search:

        like = f"%{search}%"

        query = query.filter(
            db.or_(
                Patient.patient_no.ilike(
                    like
                ),
                Patient.name.ilike(
                    like
                ),
                Patient.phone.ilike(
                    like
                )
            )
        )

    patient_list = query.order_by(
        Patient.archived,
        Patient.name
    ).all()

    return render_template(
        "patients.html",
        patients=patient_list,
        search=search
    )


@app.route(
    "/patient/<int:patient_id>"
)
@login_required
def patient_detail(
    patient_id
):

    patient = db.get_or_404(
        Patient,
        patient_id
    )

    appointments = (
        Appointment.query
        .filter_by(
            patient_id=patient.id
        )
        .order_by(
            Appointment.appointment_date.desc(),
            Appointment.scheduled_time.desc()
        )
        .all()
    )

    return render_template(
        "patient_detail.html",
        patient=patient,
        appointments=appointments
    )


@app.post(
    "/patient/<int:patient_id>/archive"
)
@role_required(
    "Admin",
    "Receptionist"
)
def archive_patient(
    patient_id
):

    patient = db.get_or_404(
        Patient,
        patient_id
    )

    patient.archived = True

    db.session.commit()

    flash(
        "Patient archived successfully.",
        "success"
    )

    return redirect(
        url_for("patients")
    )


@app.post(
    "/patient/<int:patient_id>/restore"
)
@role_required(
    "Admin",
    "Receptionist"
)
def restore_patient(
    patient_id
):

    patient = db.get_or_404(
        Patient,
        patient_id
    )

    patient.archived = False

    db.session.commit()

    flash(
        "Patient restored successfully.",
        "success"
    )

    return redirect(
        url_for("patients")
    )


@app.post(
    "/patient/<int:patient_id>/delete"
)
@role_required("Admin")
def delete_patient(
    patient_id
):

    patient = db.get_or_404(
        Patient,
        patient_id
    )

    appointment_count = (
        Appointment.query
        .filter_by(
            patient_id=patient.id
        )
        .count()
    )

    if appointment_count > 0:

        flash(
            "This patient cannot be permanently deleted because appointment history exists. Please use Archive instead.",
            "danger"
        )

        return redirect(
            url_for("patients")
        )

    db.session.delete(patient)

    db.session.commit()

    flash(
        "Patient permanently deleted.",
        "success"
    )

    return redirect(
        url_for("patients")
    )


# =========================================================
# APPOINTMENTS
# =========================================================

@app.route("/appointments")
@login_required
def appointments():

    query = Appointment.query

    if (
        current_user.role
        == "Doctor"
        and
        current_user.doctor_id
    ):

        query = query.filter_by(
            doctor_id=current_user.doctor_id
        )

    rows = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.scheduled_time.desc()
    ).all()

    return render_template(
        "appointments.html",
        appointments=rows
    )


@app.route(
    "/appointment/new",
    methods=[
        "GET",
        "POST"
    ]
)
@role_required(
    "Admin",
    "Receptionist"
)
def new_appointment():

    selected_date_text = request.args.get(
        "date",
        ""
    )

    selected_date = None
    slots = []

    if selected_date_text:

        try:

            selected_date = (
                datetime.strptime(
                    selected_date_text,
                    "%Y-%m-%d"
                ).date()
            )

            slots = generate_slots(
                selected_date
            )

        except ValueError:

            selected_date = None

    doctors = Doctor.query.filter_by(
        active=True,
        archived=False
    ).order_by(
        Doctor.name
    ).all()

    if request.method == "POST":

        patient_no = request.form[
            "patient_no"
        ].strip()

        patient_name = request.form[
            "patient_name"
        ].strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        selected_date = datetime.strptime(
            request.form[
                "appointment_date"
            ],
            "%Y-%m-%d"
        ).date()

        slot_time = datetime.strptime(
            request.form[
                "scheduled_time"
            ],
            "%H:%M"
        ).time()

        requested_doctor = request.form.get(
            "doctor_id",
            ""
        ).strip()

        duration = get_slot_duration(
            selected_date
        )

        valid_slots = generate_slots(
            selected_date
        )

        valid_slot = next(
            (
                slot
                for slot in valid_slots
                if slot["time"] == slot_time
            ),
            None
        )

        if (
            not valid_slot
            or
            valid_slot["status"]
            != "AVAILABLE"
        ):

            flash(
                "The selected appointment slot is no longer available.",
                "danger"
            )

            return redirect(
                url_for(
                    "new_appointment",
                    date=selected_date.isoformat()
                )
            )

        patient = Patient.query.filter_by(
            patient_no=patient_no
        ).first()

        if patient:

            if patient.archived:

                flash(
                    "This patient is archived. Please restore the patient before creating a new appointment.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "new_appointment",
                        date=selected_date.isoformat()
                    )
                )

            patient.name = patient_name
            patient.phone = phone

        else:

            patient = Patient(
                patient_no=patient_no,
                name=patient_name,
                phone=phone
            )

            db.session.add(patient)

            db.session.flush()

        available = available_doctors(
            selected_date,
            slot_time,
            duration
        )

        available_ids = [
            str(doctor.id)
            for doctor, workload
            in available
        ]

        if requested_doctor:

            if requested_doctor not in available_ids:

                flash(
                    "Selected doctor is not available for this slot.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "new_appointment",
                        date=selected_date.isoformat()
                    )
                )

            doctor_id = int(
                requested_doctor
            )

        else:

            if not available:

                flash(
                    "No doctor is available for this appointment slot.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "new_appointment",
                        date=selected_date.isoformat()
                    )
                )

            doctor_id = available[0][0].id

        appointment = Appointment(

            patient_id=patient.id,

            doctor_id=doctor_id,

            appointment_date=selected_date,

            scheduled_time=slot_time,

            duration_minutes=duration,

            queue_number=next_queue_number(
                selected_date
            ),

            status="Scheduled"
        )

        db.session.add(
            appointment
        )

        db.session.commit()

        flash(
            f"Appointment created successfully. Queue number: {appointment.queue_number}",
            "success"
        )

        return redirect(
            url_for("appointments")
        )

    return render_template(
        "appointment_form.html",
        doctors=doctors,
        appointment=None,
        selected_date=selected_date,
        selected_date_text=selected_date_text,
        slots=slots
    )


@app.route(
    "/appointment/<int:appointment_id>/reschedule",
    methods=[
        "GET",
        "POST"
    ]
)
@role_required(
    "Admin",
    "Receptionist"
)
def reschedule_appointment(
    appointment_id
):

    appointment = db.get_or_404(
        Appointment,
        appointment_id
    )

    selected_date_text = request.args.get(
        "date",
        appointment.appointment_date.isoformat()
    )

    selected_date = datetime.strptime(
        selected_date_text,
        "%Y-%m-%d"
    ).date()

    slots = generate_slots(
        selected_date
    )

    doctors = Doctor.query.filter_by(
        active=True,
        archived=False
    ).order_by(
        Doctor.name
    ).all()

    if request.method == "POST":

        new_date = datetime.strptime(
            request.form[
                "appointment_date"
            ],
            "%Y-%m-%d"
        ).date()

        new_time = datetime.strptime(
            request.form[
                "scheduled_time"
            ],
            "%H:%M"
        ).time()

        requested_doctor = request.form.get(
            "doctor_id",
            ""
        ).strip()

        duration = get_slot_duration(
            new_date
        )

        available = available_doctors(
            new_date,
            new_time,
            duration,
            exclude_id=appointment.id
        )

        available_ids = [
            str(doctor.id)
            for doctor, workload
            in available
        ]

        if requested_doctor:

            if requested_doctor not in available_ids:

                flash(
                    "Selected doctor is not available for this slot.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "reschedule_appointment",
                        appointment_id=appointment.id,
                        date=new_date.isoformat()
                    )
                )

            doctor_id = int(
                requested_doctor
            )

        else:

            if not available:

                flash(
                    "No doctor is available for this appointment slot.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "reschedule_appointment",
                        appointment_id=appointment.id,
                        date=new_date.isoformat()
                    )
                )

            doctor_id = available[0][0].id

        appointment.appointment_date = (
            new_date
        )

        appointment.scheduled_time = (
            new_time
        )

        appointment.duration_minutes = (
            duration
        )

        appointment.doctor_id = (
            doctor_id
        )

        appointment.status = (
            "Scheduled"
        )

        appointment.check_in_time = None
        appointment.called_time = None
        appointment.consultation_start = None
        appointment.consultation_end = None

        db.session.commit()

        flash(
            "Appointment rescheduled successfully.",
            "success"
        )

        return redirect(
            url_for("appointments")
        )

    return render_template(
        "appointment_form.html",
        doctors=doctors,
        appointment=appointment,
        selected_date=selected_date,
        selected_date_text=selected_date_text,
        slots=slots
    )


@app.post(
    "/appointment/<int:appointment_id>/action"
)
@login_required
def appointment_action(
    appointment_id
):

    appointment = db.get_or_404(
        Appointment,
        appointment_id
    )

    if (
        current_user.role
        == "Doctor"
        and
        current_user.doctor_id
        != appointment.doctor_id
    ):
        abort(403)

    action = request.form[
        "action"
    ]

    now = malaysia_now()

    if (
        action == "checkin"
        and
        current_user.role
        in [
            "Admin",
            "Receptionist"
        ]
    ):

        appointment.check_in_time = now
        appointment.status = "Checked In"

    elif (
        action == "call"
        and
        current_user.role
        in [
            "Admin",
            "Receptionist",
            "Doctor"
        ]
    ):

        appointment.called_time = now
        appointment.status = "Called"

    elif (
        action == "start"
        and
        current_user.role
        in [
            "Admin",
            "Doctor"
        ]
    ):

        appointment.consultation_start = now
        appointment.status = (
            "In Consultation"
        )

    elif (
        action == "complete"
        and
        current_user.role
        in [
            "Admin",
            "Doctor"
        ]
    ):

        appointment.consultation_end = now
        appointment.status = "Completed"

    elif (
        action == "noshow"
        and
        current_user.role
        in [
            "Admin",
            "Receptionist"
        ]
    ):

        appointment.status = "No Show"

    elif (
        action == "cancel"
        and
        current_user.role
        in [
            "Admin",
            "Receptionist"
        ]
    ):

        appointment.status = "Cancelled"

    else:

        abort(403)

    db.session.commit()

    return redirect(
        request.referrer
        or
        url_for("appointments")
    )


# =========================================================
# QUEUE
# =========================================================

@app.route("/queue")
@login_required
def queue_board():

    today = malaysia_today()

    query = Appointment.query.filter(
        Appointment.appointment_date
        == today,

        Appointment.status.in_(
            [
                "Checked In",
                "Called",
                "In Consultation"
            ]
        )
    )

    if (
        current_user.role
        == "Doctor"
        and
        current_user.doctor_id
    ):

        query = query.filter_by(
            doctor_id=current_user.doctor_id
        )

    rows = query.order_by(
        Appointment.scheduled_time
    ).all()

    return render_template(
        "queue.html",
        appointments=rows
    )


# =========================================================
# DOCTOR MANAGEMENT
# =========================================================

@app.route("/doctors")
@role_required("Admin")
def doctors():

    doctor_list = Doctor.query.order_by(
        Doctor.archived,
        Doctor.name
    ).all()

    return render_template(
        "doctors.html",
        doctors=doctor_list
    )


@app.post("/doctor/add")
@role_required("Admin")
def add_doctor():

    name = request.form[
        "name"
    ].strip()

    room = request.form.get(
        "room",
        ""
    ).strip()

    username = request.form[
        "username"
    ].strip()

    password = request.form[
        "password"
    ]

    if len(password) < 8:

        flash(
            "Temporary password must contain at least 8 characters.",
            "danger"
        )

        return redirect(
            url_for("doctors")
        )

    existing_user = User.query.filter_by(
        username=username
    ).first()

    if existing_user:

        flash(
            "Username already exists. Please choose another username.",
            "danger"
        )

        return redirect(
            url_for("doctors")
        )

    doctor = Doctor(
        name=name,
        room=room,
        active=True,
        archived=False
    )

    db.session.add(doctor)
    db.session.flush()

    user = User(
        username=username,
        role="Doctor",
        doctor_id=doctor.id,
        enabled=True
    )

    user.set_password(
        password
    )

    db.session.add(user)

    db.session.commit()

    flash(
        "Doctor and login account created successfully.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.post(
    "/doctor/<int:doctor_id>/toggle"
)
@role_required("Admin")
def toggle_doctor(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    if doctor.archived:

        flash(
            "Archived doctor must be restored before activation.",
            "warning"
        )

        return redirect(
            url_for("doctors")
        )

    doctor.active = (
        not doctor.active
    )

    user = User.query.filter_by(
        doctor_id=doctor.id,
        role="Doctor"
    ).first()

    if user:

        user.enabled = (
            doctor.active
        )

    db.session.commit()

    flash(
        "Doctor status updated.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.post(
    "/doctor/<int:doctor_id>/archive"
)
@role_required("Admin")
def archive_doctor(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    doctor.archived = True
    doctor.active = False

    user = User.query.filter_by(
        doctor_id=doctor.id,
        role="Doctor"
    ).first()

    if user:

        user.enabled = False

    db.session.commit()

    flash(
        "Doctor archived successfully.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.post(
    "/doctor/<int:doctor_id>/restore"
)
@role_required("Admin")
def restore_doctor(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    doctor.archived = False
    doctor.active = True

    user = User.query.filter_by(
        doctor_id=doctor.id,
        role="Doctor"
    ).first()

    if user:

        user.enabled = True

    db.session.commit()

    flash(
        "Doctor restored successfully.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.post(
    "/doctor/<int:doctor_id>/delete"
)
@role_required("Admin")
def delete_doctor(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    appointment_count = (
        Appointment.query
        .filter_by(
            doctor_id=doctor.id
        )
        .count()
    )

    if appointment_count > 0:

        flash(
            "This doctor cannot be permanently deleted because appointment history exists. Please use Archive instead.",
            "danger"
        )

        return redirect(
            url_for("doctors")
        )

    user = User.query.filter_by(
        doctor_id=doctor.id,
        role="Doctor"
    ).first()

    if user:
        db.session.delete(user)

    DoctorSchedule.query.filter_by(
        doctor_id=doctor.id
    ).delete()

    DoctorLeave.query.filter_by(
        doctor_id=doctor.id
    ).delete()

    db.session.delete(doctor)

    db.session.commit()

    flash(
        "Doctor permanently deleted.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


@app.post(
    "/doctor/<int:doctor_id>/reset-password"
)
@role_required("Admin")
def reset_doctor_password(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    new_password = request.form[
        "new_password"
    ]

    if len(new_password) < 8:

        flash(
            "New password must contain at least 8 characters.",
            "danger"
        )

        return redirect(
            url_for("doctors")
        )

    user = User.query.filter_by(
        doctor_id=doctor.id,
        role="Doctor"
    ).first()

    if not user:

        flash(
            "This doctor does not have a login account.",
            "danger"
        )

        return redirect(
            url_for("doctors")
        )

    user.set_password(
        new_password
    )

    db.session.commit()

    flash(
        "Doctor password reset successfully.",
        "success"
    )

    return redirect(
        url_for("doctors")
    )


# =========================================================
# DOCTOR SCHEDULE
# =========================================================

@app.route(
    "/doctor/<int:doctor_id>/schedule",
    methods=[
        "GET",
        "POST"
    ]
)
@role_required("Admin")
def doctor_schedule(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    if request.method == "POST":

        weekday = int(
            request.form[
                "weekday"
            ]
        )

        start_time = datetime.strptime(
            request.form[
                "start_time"
            ],
            "%H:%M"
        ).time()

        end_time = datetime.strptime(
            request.form[
                "end_time"
            ],
            "%H:%M"
        ).time()

        if end_time <= start_time:

            flash(
                "End time must be later than start time.",
                "danger"
            )

            return redirect(
                url_for(
                    "doctor_schedule",
                    doctor_id=doctor.id
                )
            )

        schedule = DoctorSchedule(

            doctor_id=doctor.id,

            weekday=weekday,

            start_time=start_time,

            end_time=end_time
        )

        db.session.add(
            schedule
        )

        db.session.commit()

        flash(
            "Doctor schedule added.",
            "success"
        )

        return redirect(
            url_for(
                "doctor_schedule",
                doctor_id=doctor.id
            )
        )

    schedules = (
        DoctorSchedule.query
        .filter_by(
            doctor_id=doctor.id
        )
        .order_by(
            DoctorSchedule.weekday,
            DoctorSchedule.start_time
        )
        .all()
    )

    return render_template(
        "doctor_schedule.html",
        doctor=doctor,
        schedules=schedules
    )


@app.post(
    "/schedule/<int:schedule_id>/delete"
)
@role_required("Admin")
def delete_schedule(
    schedule_id
):

    schedule = db.get_or_404(
        DoctorSchedule,
        schedule_id
    )

    doctor_id = (
        schedule.doctor_id
    )

    db.session.delete(
        schedule
    )

    db.session.commit()

    return redirect(
        url_for(
            "doctor_schedule",
            doctor_id=doctor_id
        )
    )


# =========================================================
# DOCTOR LEAVE
# =========================================================

@app.route(
    "/doctor/<int:doctor_id>/leave",
    methods=[
        "GET",
        "POST"
    ]
)
@role_required("Admin")
def doctor_leave(
    doctor_id
):

    doctor = db.get_or_404(
        Doctor,
        doctor_id
    )

    if request.method == "POST":

        leave_date = datetime.strptime(
            request.form[
                "leave_date"
            ],
            "%Y-%m-%d"
        ).date()

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        leave = DoctorLeave(

            doctor_id=doctor.id,

            leave_date=leave_date,

            reason=reason
        )

        db.session.add(
            leave
        )

        db.session.commit()

        flash(
            "Doctor leave added.",
            "success"
        )

        return redirect(
            url_for(
                "doctor_leave",
                doctor_id=doctor.id
            )
        )

    leaves = (
        DoctorLeave.query
        .filter_by(
            doctor_id=doctor.id
        )
        .order_by(
            DoctorLeave.leave_date.desc()
        )
        .all()
    )

    return render_template(
        "doctor_leave.html",
        doctor=doctor,
        leaves=leaves
    )


@app.post(
    "/leave/<int:leave_id>/delete"
)
@role_required("Admin")
def delete_leave(
    leave_id
):

    leave = db.get_or_404(
        DoctorLeave,
        leave_id
    )

    doctor_id = (
        leave.doctor_id
    )

    db.session.delete(
        leave
    )

    db.session.commit()

    return redirect(
        url_for(
            "doctor_leave",
            doctor_id=doctor_id
        )
    )


# =========================================================
# AVAILABILITY / SLOT VIEW
# =========================================================

@app.route("/availability")
@role_required(
    "Admin",
    "Receptionist"
)
def availability():

    date_text = request.args.get(
        "date",
        ""
    )

    selected_date = None
    slots = []

    if date_text:

        try:

            selected_date = (
                datetime.strptime(
                    date_text,
                    "%Y-%m-%d"
                ).date()
            )

            slots = generate_slots(
                selected_date
            )

        except ValueError:

            selected_date = None

    return render_template(
        "availability.html",
        selected_date=selected_date,
        date_text=date_text,
        slots=slots
    )


# =========================================================
# ADMIN SETTINGS / SLOT MANAGEMENT
# =========================================================

@app.route(
    "/settings",
    methods=[
        "GET",
        "POST"
    ]
)
@role_required("Admin")
def settings():

    setting = get_system_setting()

    if request.method == "POST":

        default_duration = int(
            request.form[
                "default_slot_minutes"
            ]
        )

        if default_duration not in [
            5,
            10,
            15,
            20,
            30,
            45,
            60
        ]:

            flash(
                "Invalid default slot duration.",
                "danger"
            )

            return redirect(
                url_for("settings")
            )

        setting.default_slot_minutes = (
            default_duration
        )

        db.session.commit()

        flash(
            "Default slot duration updated.",
            "success"
        )

        return redirect(
            url_for("settings")
        )

    date_settings = (
        DateSlotSetting.query
        .order_by(
            DateSlotSetting.setting_date.desc()
        )
        .all()
    )

    blocked_slots = (
        BlockedSlot.query
        .order_by(
            BlockedSlot.block_date.desc(),
            BlockedSlot.block_time
        )
        .all()
    )

    return render_template(
        "settings.html",
        setting=setting,
        date_settings=date_settings,
        blocked_slots=blocked_slots
    )


@app.post(
    "/settings/date-slot"
)
@role_required("Admin")
def add_date_slot_setting():

    setting_date = datetime.strptime(
        request.form[
            "setting_date"
        ],
        "%Y-%m-%d"
    ).date()

    slot_minutes = int(
        request.form[
            "slot_minutes"
        ]
    )

    existing = (
        DateSlotSetting.query
        .filter_by(
            setting_date=setting_date
        )
        .first()
    )

    if existing:

        existing.slot_minutes = (
            slot_minutes
        )

    else:

        db.session.add(
            DateSlotSetting(
                setting_date=setting_date,
                slot_minutes=slot_minutes
            )
        )

    db.session.commit()

    flash(
        "Date-specific slot duration saved.",
        "success"
    )

    return redirect(
        url_for("settings")
    )


@app.post(
    "/settings/date-slot/<int:setting_id>/delete"
)
@role_required("Admin")
def delete_date_slot_setting(
    setting_id
):

    setting = db.get_or_404(
        DateSlotSetting,
        setting_id
    )

    db.session.delete(
        setting
    )

    db.session.commit()

    flash(
        "Date-specific slot setting removed.",
        "success"
    )

    return redirect(
        url_for("settings")
    )


@app.post(
    "/settings/block-slot"
)
@role_required("Admin")
def block_slot():

    block_date = datetime.strptime(
        request.form[
            "block_date"
        ],
        "%Y-%m-%d"
    ).date()

    block_time = datetime.strptime(
        request.form[
            "block_time"
        ],
        "%H:%M"
    ).time()

    reason = request.form.get(
        "reason",
        ""
    ).strip()

    existing = BlockedSlot.query.filter_by(
        block_date=block_date,
        block_time=block_time
    ).first()

    if existing:

        flash(
            "This slot is already blocked.",
            "warning"
        )

        return redirect(
            url_for("settings")
        )

    db.session.add(
        BlockedSlot(
            block_date=block_date,
            block_time=block_time,
            reason=reason
        )
    )

    db.session.commit()

    flash(
        "Appointment slot blocked.",
        "success"
    )

    return redirect(
        url_for("settings")
    )


@app.post(
    "/settings/block-slot/<int:block_id>/delete"
)
@role_required("Admin")
def unblock_slot(
    block_id
):

    blocked = db.get_or_404(
        BlockedSlot,
        block_id
    )

    db.session.delete(
        blocked
    )

    db.session.commit()

    flash(
        "Appointment slot unblocked.",
        "success"
    )

    return redirect(
        url_for("settings")
    )


# =========================================================
# DATABASE MIGRATION / INITIAL DATA
# =========================================================

def add_column_if_missing(
    table_name,
    column_name,
    column_sql
):

    inspector = inspect(
        db.engine
    )

    columns = [
        column["name"]
        for column
        in inspector.get_columns(
            table_name
        )
    ]

    if column_name not in columns:

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    f'''
                    ALTER TABLE "{table_name}"
                    ADD COLUMN "{column_name}"
                    {column_sql}
                    '''
                )
            )


def seed():

    db.create_all()

    add_column_if_missing(
        "doctor",
        "archived",
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )

    add_column_if_missing(
        "patient",
        "archived",
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )

    add_column_if_missing(
        "user",
        "enabled",
        "BOOLEAN NOT NULL DEFAULT TRUE"
    )

    if not SystemSetting.query.first():

        db.session.add(
            SystemSetting(
                default_slot_minutes=30
            )
        )

    admin = User.query.filter_by(
        username="admin"
    ).first()

    if not admin:

        admin = User(
            username="admin",
            role="Admin",
            enabled=True
        )

        admin.set_password(
            "admin123"
        )

        db.session.add(admin)

    receptionist = User.query.filter_by(
        username="receptionist"
    ).first()

    if not receptionist:

        receptionist = User(
            username="receptionist",
            role="Receptionist",
            enabled=True
        )

        receptionist.set_password(
            "reception123"
        )

        db.session.add(
            receptionist
        )

    # Remove old demo doctor login accounts.
    legacy_users = User.query.filter(
        User.username.in_(
            [
                "doctor1",
                "doctor2",
                "doctor3"
            ]
        ),
        User.role == "Doctor"
    ).all()

    for legacy_user in legacy_users:

        db.session.delete(
            legacy_user
        )

    db.session.commit()


with app.app_context():

    seed()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )