import os, re, secrets
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, IntegerField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, EqualTo, ValidationError
from config import Config
from models import db, User, MaidProfile, EmployerProfile, Skill, HiringRequest, Favourite, Review, Report, ChatMessage, DirectConversation, DirectMessage

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SKILL_NAMES = ["Cooking", "Cleaning", "Washing Clothes", "Ironing", "Babysitting", "Elderly Care", "All Household Work"]
JOB_TYPES = ["Full-time", "Part-time", "Live-in", "Live-out"]

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    CSRFProtect(app)

    def current_user():
        uid = session.get("user_id")
        return db.session.get(User, uid) if uid else None
    app.jinja_env.globals["current_user"] = current_user

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user or not user.is_active:
                session.clear()
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapped

    def role_required(*roles):
        def decorator(fn):
            @wraps(fn)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user().role not in roles:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def valid_mobile(value):
        return bool(re.fullmatch(r"[0-9+\-\s]{8,20}", value or ""))

    def upload_photo(file):
        if not file or not file.filename:
            return None
        filename = secure_filename(file.filename)
        if "." not in filename or filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("Photo must be PNG, JPG, JPEG, or WEBP.")
        ext = filename.rsplit(".", 1)[1].lower()
        safe_name = secrets.token_hex(16) + "." + ext
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], safe_name))
        return safe_name

    @app.route("/")
    def index():
        city = request.args.get("city", "").strip()
        q = MaidProfile.query.join(User).filter(User.is_active.is_(True), MaidProfile.is_available.is_(True), MaidProfile.consent_public_profile.is_(True))
        if city:
            q = q.filter(MaidProfile.city.ilike(f"%{city}%"))
        maids = q.order_by(User.created_at.desc()).limit(8).all()
        return render_template("index.html", maids=maids)

    @app.route("/register/maid", methods=["GET", "POST"])
    def register_maid():
        if request.method == "POST":
            f = request.form
            name, mobile = f.get("full_name","").strip(), f.get("mobile","").strip()
            email = f.get("email","").strip().lower() or None
            password = f.get("password","")
            try:
                age, exp, salary = int(f.get("age","0")), int(f.get("experience_years","0")), int(f.get("expected_salary","0"))
                if not 18 <= age <= 80: raise ValueError("Age must be between 18 and 80.")
                if exp < 0 or salary < 0: raise ValueError("Experience and salary cannot be negative.")
                if not valid_mobile(mobile): raise ValueError("Enter a valid mobile number.")
                if len(password) < 8: raise ValueError("Password must be at least 8 characters.")
                if password != f.get("confirm_password"): raise ValueError("Passwords do not match.")
                if User.query.filter_by(mobile=mobile).first(): raise ValueError("Mobile number already registered.")
                if email and User.query.filter_by(email=email).first(): raise ValueError("Email already registered.")
                photo = upload_photo(request.files.get("photo"))
                user = User(full_name=name, mobile=mobile, email=email, password_hash=generate_password_hash(password), role="maid")
                profile = MaidProfile(age=age, gender=f.get("gender","Female"), address=f.get("address","").strip(),
                    city=f.get("city","").strip(), state=f.get("state","").strip(), photo=photo,
                    experience_years=exp, expected_salary=salary, working_hours=f.get("working_hours","Flexible"),
                    job_type=f.get("job_type","Part-time"), languages=f.get("languages","").strip(),
                    available_from=f.get("available_from",""), previous_experience=f.get("previous_experience","").strip(),
                    reference_details=f.get("reference_details","").strip(), consent_public_profile=bool(f.get("consent_public_profile")))
                user.maid_profile = profile
                for name_skill in request.form.getlist("skills"):
                    skill = Skill.query.filter_by(name=name_skill).first()
                    if skill and skill not in profile.skills: profile.skills.append(skill)
                db.session.add(user); db.session.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except (ValueError, TypeError) as e:
                db.session.rollback(); flash(str(e), "danger")
            except Exception:
                db.session.rollback(); flash("Could not register. Check your details and try again.", "danger")
        return render_template("maid_register.html", skills=SKILL_NAMES, job_types=JOB_TYPES)

    @app.route("/register/employer", methods=["GET", "POST"])
    def register_employer():
        if request.method == "POST":
            f = request.form
            name, mobile = f.get("full_name","").strip(), f.get("mobile","").strip()
            email = f.get("email","").strip().lower() or None
            password = f.get("password","")
            try:
                budget = int(f.get("budget","0"))
                if not valid_mobile(mobile): raise ValueError("Enter a valid mobile number.")
                if len(password) < 8: raise ValueError("Password must be at least 8 characters.")
                if password != f.get("confirm_password"): raise ValueError("Passwords do not match.")
                if budget < 0: raise ValueError("Budget cannot be negative.")
                if User.query.filter_by(mobile=mobile).first(): raise ValueError("Mobile number already registered.")
                if email and User.query.filter_by(email=email).first(): raise ValueError("Email already registered.")
                user = User(full_name=name, mobile=mobile, email=email, password_hash=generate_password_hash(password), role="employer")
                user.employer_profile = EmployerProfile(house_address=f.get("house_address","").strip(), city=f.get("city","").strip(),
                    state=f.get("state","").strip(), preferred_maid_type=f.get("preferred_maid_type","Any"),
                    required_services=", ".join(request.form.getlist("required_services")),
                    expected_hours=f.get("expected_hours",""), budget=budget,
                    preferred_joining_date=f.get("preferred_joining_date",""), additional_requirements=f.get("additional_requirements","").strip())
                db.session.add(user); db.session.commit()
                flash("Employer registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except (ValueError, TypeError) as e:
                db.session.rollback(); flash(str(e), "danger")
            except Exception:
                db.session.rollback(); flash("Could not register. Check your details and try again.", "danger")
        return render_template("employer_register.html", skills=SKILL_NAMES, job_types=JOB_TYPES)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            identity = request.form.get("identity","").strip()
            user = User.query.filter(or_(User.mobile == identity, User.email == identity.lower())).first()
            if user and user.is_active and check_password_hash(user.password_hash, request.form.get("password","")):
                session.clear(); session["user_id"] = user.id
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid credentials or inactive account.", "danger")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear(); flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        if user.role == "maid": return render_template("maid_dashboard.html", user=user,
            requests=HiringRequest.query.filter_by(maid_id=user.id).order_by(HiringRequest.created_at.desc()).all())
        if user.role == "employer": return render_template("employer_dashboard.html", user=user,
            requests=HiringRequest.query.filter_by(employer_id=user.id).order_by(HiringRequest.created_at.desc()).all(),
            favourites=Favourite.query.filter_by(employer_id=user.id).all())
        return redirect(url_for("admin_dashboard"))

    @app.route("/maids")
    @role_required("employer", "admin")
    def maid_list():
        q = MaidProfile.query.join(User).filter(User.is_active.is_(True), MaidProfile.is_available.is_(True), MaidProfile.consent_public_profile.is_(True))
        city, term = request.args.get("city","").strip(), request.args.get("q","").strip()
        min_exp, max_salary = request.args.get("min_exp","").strip(), request.args.get("max_salary","").strip()
        skill = request.args.get("skill","").strip()
        job_type = request.args.get("job_type","").strip()
        if city: q = q.filter(MaidProfile.city.ilike(f"%{city}%"))
        if term: q = q.filter(or_(User.full_name.ilike(f"%{term}%"), MaidProfile.city.ilike(f"%{term}%")))
        if min_exp:
            try: q = q.filter(MaidProfile.experience_years >= int(min_exp))
            except ValueError: pass
        if max_salary:
            try: q = q.filter(MaidProfile.expected_salary <= int(max_salary))
            except ValueError: pass
        if skill: q = q.filter(MaidProfile.skills.any(Skill.name == skill))
        if job_type: q = q.filter(MaidProfile.job_type == job_type)
        return render_template("maid_list.html", maids=q.order_by(MaidProfile.expected_salary.asc()).all(),
                               skills=SKILL_NAMES, job_types=JOB_TYPES)

    @app.route("/maids/<int:maid_id>")
    @login_required
    def maid_profile(maid_id):
        maid = db.session.get(User, maid_id)
        if not maid or maid.role != "maid" or not maid.maid_profile or not maid.maid_profile.consent_public_profile: abort(404)
        reviews = Review.query.filter_by(maid_user_id=maid.id, is_hidden=False).order_by(Review.created_at.desc()).all()
        return render_template("maid_profile.html", maid=maid, reviews=reviews)

    @app.route("/profile", methods=["GET", "POST"])
    @role_required("maid")
    def edit_profile():
        user = current_user(); p = user.maid_profile
        if request.method == "POST":
            try:
                p.city = request.form.get("city", p.city).strip()
                p.state = request.form.get("state", p.state).strip()
                p.expected_salary = int(request.form.get("expected_salary", p.expected_salary))
                p.is_available = request.form.get("is_available") == "yes"
                p.languages = request.form.get("languages", p.languages).strip()
                photo = upload_photo(request.files.get("photo"))
                if photo: p.photo = photo
                db.session.commit(); flash("Profile updated.", "success"); return redirect(url_for("dashboard"))
            except (ValueError, TypeError) as e:
                db.session.rollback(); flash(str(e), "danger")
        return render_template("edit_profile.html", p=p)

    @app.route("/hire/<int:maid_id>", methods=["GET", "POST"])
    @role_required("employer")
    def hire(maid_id):
        maid = db.session.get(User, maid_id)
        if not maid or maid.role != "maid" or not maid.maid_profile or not maid.maid_profile.is_available: abort(404)
        if request.method == "POST":
            try:
                salary = int(request.form.get("salary_offered","0"))
                if salary < 0: raise ValueError("Salary must be zero or greater.")
                existing = HiringRequest.query.filter_by(employer_id=current_user().id, maid_id=maid.id).filter(HiringRequest.status.in_(["Pending","Accepted"])).first()
                if existing: raise ValueError("You already have an active request for this maid.")
                conflict = HiringRequest.query.filter_by(maid_id=maid.id, status="Accepted").first()
                if conflict: raise ValueError("This maid already has an accepted booking.")
                req = HiringRequest(employer_id=current_user().id, maid_id=maid.id,
                    job_location=request.form.get("job_location","").strip(), salary_offered=salary,
                    work_timings=request.form.get("work_timings","").strip(), job_description=request.form.get("job_description","").strip())
                db.session.add(req); db.session.commit(); flash("Hiring request sent.", "success")
                return redirect(url_for("dashboard"))
            except (ValueError, TypeError) as e:
                db.session.rollback(); flash(str(e), "danger")
        return render_template("hire.html", maid=maid)

    @app.route("/requests/<int:req_id>/<action>", methods=["POST"])
    @login_required
    def update_request(req_id, action):
        req = db.session.get(HiringRequest, req_id); user = current_user()
        if not req: abort(404)
        if action == "cancel" and user.role == "employer" and req.employer_id == user.id and req.status == "Pending":
            req.status = "Cancelled"
        elif action in ("accept", "reject") and user.role == "maid" and req.maid_id == user.id and req.status == "Pending":
            if action == "accept":
                other = HiringRequest.query.filter(HiringRequest.maid_id == user.id, HiringRequest.status == "Accepted", HiringRequest.id != req.id).first()
                if other: flash("You already have an accepted booking.", "warning"); return redirect(url_for("dashboard"))
                req.status = "Accepted"
            else: req.status = "Rejected"
        elif action == "complete" and user.role == "employer" and req.employer_id == user.id and req.status == "Accepted":
            req.status = "Completed"
            maid = req.maid
            if maid and maid.maid_profile: maid.maid_profile.is_available = True
        else: abort(403)
        db.session.commit(); flash(f"Request marked {req.status.lower()}.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/messages")
    @login_required
    def messages_inbox():
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        if user.role == "maid":
            requests = HiringRequest.query.filter_by(maid_id=user.id).order_by(HiringRequest.updated_at.desc()).all()
        else:
            requests = HiringRequest.query.filter_by(employer_id=user.id).order_by(HiringRequest.updated_at.desc()).all()
        conversations = []
        for req in requests:
            other_user = req.employer if user.role == "maid" else req.maid
            last_message = ChatMessage.query.filter_by(hiring_request_id=req.id).order_by(ChatMessage.created_at.desc()).first()
            unread_count = ChatMessage.query.filter_by(hiring_request_id=req.id, is_read=False).filter(
                ChatMessage.sender_id != user.id
            ).count()
            conversations.append({"request": req, "other_user": other_user,
                                  "last_message": last_message, "unread_count": unread_count})
        direct_conversations = DirectConversation.query.filter(
            or_(DirectConversation.user_one_id == user.id, DirectConversation.user_two_id == user.id)
        ).order_by(DirectConversation.updated_at.desc()).all()
        direct_items = []
        for conversation in direct_conversations:
            last_message = DirectMessage.query.filter_by(conversation_id=conversation.id).order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc()).first()
            unread_count = DirectMessage.query.filter_by(conversation_id=conversation.id, is_read=False).filter(
                DirectMessage.sender_id != user.id
            ).count()
            direct_items.append({
                "conversation": conversation,
                "other_user": conversation.other_user(user.id),
                "last_message": last_message,
                "unread_count": unread_count
            })
        return render_template("messages.html", conversations=conversations, direct_items=direct_items, user=user)

    @app.route("/chat/<int:req_id>", methods=["GET", "POST"])
    @login_required
    def chat(req_id):
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        req = db.session.get(HiringRequest, req_id)
        if not req or user.id not in (req.maid_id, req.employer_id):
            abort(404)
        other_user = req.employer if user.id == req.maid_id else req.maid
        can_send = True
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if not body:
                flash("Please enter a message.", "warning")
            elif len(body) > 2000:
                flash("Messages must be 2,000 characters or fewer.", "danger")
            else:
                db.session.add(ChatMessage(hiring_request_id=req.id, sender_id=user.id, body=body))
                db.session.commit()
                return redirect(url_for("chat", req_id=req.id))
        ChatMessage.query.filter_by(hiring_request_id=req.id, is_read=False).filter(
            ChatMessage.sender_id != user.id
        ).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
        chat_messages = ChatMessage.query.filter_by(hiring_request_id=req.id).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
        return render_template("chat.html", req=req, other_user=other_user, chat_messages=chat_messages,
                               can_send=can_send, user=user)

    @app.route("/chat/<int:req_id>/updates")
    @login_required
    def chat_updates(req_id):
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        req = db.session.get(HiringRequest, req_id)
        if not req or user.id not in (req.maid_id, req.employer_id):
            abort(404)
        try:
            after_id = max(0, int(request.args.get("after", "0")))
        except (TypeError, ValueError):
            after_id = 0
        new_messages = ChatMessage.query.filter(
            ChatMessage.hiring_request_id == req.id,
            ChatMessage.id > after_id
        ).order_by(ChatMessage.id.asc()).all()
        for message in new_messages:
            if message.sender_id != user.id:
                message.is_read = True
        if new_messages:
            db.session.commit()
        return jsonify({"messages": [{
            "id": message.id,
            "sender_id": message.sender_id,
            "sender_name": message.sender.full_name,
            "body": message.body,
            "created_at": message.created_at.strftime("%d %b %Y, %I:%M %p")
        } for message in new_messages]})

    @app.route("/messages/new", methods=["GET", "POST"])
    @login_required
    def new_message():
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        term = request.args.get("q", "").strip()
        role_filter = request.args.get("role", "all").strip().lower()
        query = User.query.filter(User.is_active.is_(True), User.role.in_(["maid", "employer"]), User.id != user.id)
        if role_filter in ("maid", "employer"):
            query = query.filter(User.role == role_filter)
        if term:
            query = query.filter(or_(User.full_name.ilike(f"%{term}%"),
                                     User.email.ilike(f"%{term}%")))
        people = query.order_by(User.full_name.asc()).limit(100).all()
        if request.method == "POST":
            try:
                other_id = int(request.form.get("user_id", "0"))
            except ValueError:
                abort(400)
            other = db.session.get(User, other_id)
            if not other or other.id == user.id or other.role not in ("maid", "employer") or not other.is_active:
                abort(404)
            first_id, second_id = sorted([user.id, other.id])
            conversation = DirectConversation.query.filter_by(user_one_id=first_id, user_two_id=second_id).first()
            if not conversation:
                conversation = DirectConversation(user_one_id=first_id, user_two_id=second_id)
                db.session.add(conversation)
                db.session.commit()
            return redirect(url_for("direct_chat", conversation_id=conversation.id))
        return render_template("new_message.html", people=people, role_filter=role_filter, term=term, user=user)

    @app.route("/direct-chat/<int:conversation_id>", methods=["GET", "POST"])
    @login_required
    def direct_chat(conversation_id):
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        conversation = db.session.get(DirectConversation, conversation_id)
        if not conversation or user.id not in (conversation.user_one_id, conversation.user_two_id):
            abort(404)
        other_user = conversation.other_user(user.id)
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if not body:
                flash("Please enter a message.", "warning")
            elif len(body) > 2000:
                flash("Messages must be 2,000 characters or fewer.", "danger")
            else:
                db.session.add(DirectMessage(conversation_id=conversation.id, sender_id=user.id, body=body))
                conversation.updated_at = db.func.now()
                db.session.commit()
                return redirect(url_for("direct_chat", conversation_id=conversation.id))
        DirectMessage.query.filter_by(conversation_id=conversation.id, is_read=False).filter(
            DirectMessage.sender_id != user.id
        ).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
        chat_messages = DirectMessage.query.filter_by(conversation_id=conversation.id).order_by(
            DirectMessage.created_at.asc(), DirectMessage.id.asc()
        ).all()
        return render_template("direct_chat.html", conversation=conversation, other_user=other_user,
                               chat_messages=chat_messages, user=user)

    @app.route("/direct-chat/<int:conversation_id>/updates")
    @login_required
    def direct_chat_updates(conversation_id):
        user = current_user()
        if user.role not in ("maid", "employer"):
            abort(403)
        conversation = db.session.get(DirectConversation, conversation_id)
        if not conversation or user.id not in (conversation.user_one_id, conversation.user_two_id):
            abort(404)
        try:
            after_id = max(0, int(request.args.get("after", "0")))
        except (TypeError, ValueError):
            after_id = 0
        new_messages = DirectMessage.query.filter(
            DirectMessage.conversation_id == conversation.id,
            DirectMessage.id > after_id
        ).order_by(DirectMessage.id.asc()).all()
        for message in new_messages:
            if message.sender_id != user.id:
                message.is_read = True
        if new_messages:
            db.session.commit()
        return jsonify({"messages": [{
            "id": message.id,
            "sender_id": message.sender_id,
            "sender_name": message.sender.full_name,
            "body": message.body,
            "created_at": message.created_at.strftime("%d %b %Y, %I:%M %p")
        } for message in new_messages]})

    @app.route("/favourite/<int:maid_id>", methods=["POST"])
    @role_required("employer")
    def favourite(maid_id):
        maid = db.session.get(User, maid_id)
        if not maid or maid.role != "maid": abort(404)
        existing = Favourite.query.filter_by(employer_id=current_user().id, maid_id=maid_id).first()
        if existing: db.session.delete(existing); flash("Removed from favourites.", "info")
        else: db.session.add(Favourite(employer_id=current_user().id, maid_id=maid_id)); flash("Added to favourites.", "success")
        db.session.commit(); return redirect(request.referrer or url_for("maid_list"))

    @app.route("/review/<int:req_id>", methods=["GET", "POST"])
    @role_required("employer")
    def review(req_id):
        req = db.session.get(HiringRequest, req_id)
        if not req or req.employer_id != current_user().id or req.status != "Completed": abort(403)
        if Review.query.filter_by(hiring_request_id=req.id).first(): flash("A review already exists.", "warning"); return redirect(url_for("dashboard"))
        if request.method == "POST":
            try:
                rating = int(request.form.get("rating","0"))
                if not 1 <= rating <= 5: raise ValueError("Rating must be from 1 to 5.")
                db.session.add(Review(employer_id=current_user().id, maid_user_id=req.maid_id, hiring_request_id=req.id,
                                      rating=rating, comment=request.form.get("comment","").strip()))
                db.session.commit(); flash("Review submitted.", "success"); return redirect(url_for("dashboard"))
            except ValueError as e: flash(str(e), "danger")
        return render_template("review.html", req=req)

    @app.route("/report/<int:user_id>", methods=["POST"])
    @login_required
    def report_user(user_id):
        if user_id == current_user().id: abort(400)
        if not db.session.get(User, user_id): abort(404)
        reason = request.form.get("reason","").strip()
        if not reason: flash("Please provide a reason.", "warning")
        else:
            db.session.add(Report(reporter_id=current_user().id, reported_user_id=user_id, reason=reason[:500]))
            db.session.commit(); flash("Report submitted to the admin.", "success")
        return redirect(request.referrer or url_for("index"))

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():
        return render_template("admin_dashboard.html", users=User.query.order_by(User.created_at.desc()).all(),
            requests=HiringRequest.query.order_by(HiringRequest.created_at.desc()).limit(50).all(),
            reports=Report.query.filter_by(status="Open").all(),
            maid_count=User.query.filter_by(role="maid").count(),
            employer_count=User.query.filter_by(role="employer").count(),
            hires=HiringRequest.query.filter_by(status="Completed").count())

    @app.route("/admin/user/<int:user_id>/<action>", methods=["POST"])
    @role_required("admin")
    def admin_user_action(user_id, action):
        user = db.session.get(User, user_id)
        if not user or user.role == "admin": abort(404)
        if action == "verify": user.is_verified = True
        elif action == "suspend": user.is_active = False
        elif action == "activate": user.is_active = True
        else: abort(400)
        db.session.commit(); flash("Account updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/about")
    def about(): return render_template("page.html", title="About Us", body="We help households and domestic workers connect through a transparent hiring process. Always verify identity and references independently.")
    @app.route("/privacy")
    def privacy(): return render_template("page.html", title="Privacy Policy", body="We store account and profile information needed to operate this service. Public profiles do not show phone numbers or complete addresses. Users can deactivate their account by contacting the administrator. Set a strong SECRET_KEY before deployment.")
    @app.route("/terms")
    def terms(): return render_template("page.html", title="Terms and Conditions", body="Users must provide truthful information and treat one another respectfully. Hiring arrangements, salary, duties and safety checks should be agreed directly before work begins. This demo is not a background-check service.")
    @app.route("/contact")
    def contact(): return render_template("page.html", title="Contact Us", body="For support, contact the site administrator. Add your real support email and phone before launching publicly.")

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        for name in SKILL_NAMES:
            if not Skill.query.filter_by(name=name).first(): db.session.add(Skill(name=name))
        db.session.commit()
        print("Database initialized.")

    @app.cli.command("seed-demo")
    def seed_demo():
        db.create_all()
        for name in SKILL_NAMES:
            if not Skill.query.filter_by(name=name).first(): db.session.add(Skill(name=name))
        if not User.query.filter_by(mobile="9990000001").first():
            maid = User(full_name="Demo Maid", mobile="9990000001", email="maid@example.com",
                        password_hash=generate_password_hash("DemoPass123!"), role="maid", is_verified=True)
            maid.maid_profile = MaidProfile(age=32, gender="Female", address="Private address", city="Delhi", state="Delhi",
                experience_years=4, expected_salary=12000, working_hours="8 AM - 2 PM", job_type="Part-time",
                languages="Hindi", available_from="2026-11-01", is_available=True, consent_public_profile=True)
            maid.maid_profile.skills = Skill.query.filter(Skill.name.in_(["Cooking","Cleaning"])).all()
            db.session.add(maid)
        if not User.query.filter_by(mobile="9990000002").first():
            employer = User(full_name="Demo Employer", mobile="9990000002", email="employer@example.com",
                            password_hash=generate_password_hash("DemoPass123!"), role="employer")
            employer.employer_profile = EmployerProfile(house_address="Private address", city="Delhi", state="Delhi", budget=15000)
            db.session.add(employer)
        if not User.query.filter_by(mobile="9990000003").first():
            db.session.add(User(full_name="Demo Admin", mobile="9990000003", email="admin@example.com",
                                password_hash=generate_password_hash("AdminPass123!"), role="admin"))
        db.session.commit()

        # Seed an example hiring request and sample chat so the feature is visible
        # immediately after running `flask --app app seed-demo`.
        demo_maid = User.query.filter_by(email="maid@example.com", role="maid").first()
        demo_employer = User.query.filter_by(email="employer@example.com", role="employer").first()
        demo_request = None
        if demo_maid and demo_employer:
            demo_request = HiringRequest.query.filter(
                HiringRequest.maid_id == demo_maid.id,
                HiringRequest.employer_id == demo_employer.id,
                HiringRequest.status.in_(["Pending", "Accepted"])
            ).order_by(HiringRequest.id.desc()).first()

            if not demo_request:
                demo_request = HiringRequest(
                    employer_id=demo_employer.id,
                    maid_id=demo_maid.id,
                    job_location="Demo locality, Delhi",
                    salary_offered=12000,
                    work_timings="8 AM - 2 PM",
                    job_description="Demo request: cooking and cleaning",
                    status="Pending"
                )
                db.session.add(demo_request)
                db.session.commit()

            if ChatMessage.query.filter_by(hiring_request_id=demo_request.id).count() == 0:
                db.session.add_all([
                    ChatMessage(
                        hiring_request_id=demo_request.id,
                        sender_id=demo_employer.id,
                        body="Hello! Are you available for cooking and cleaning from next week?",
                        is_read=True
                    ),
                    ChatMessage(
                        hiring_request_id=demo_request.id,
                        sender_id=demo_maid.id,
                        body="Hello! Yes, I am available. We can discuss the timings here.",
                        is_read=True
                    )
                ])
                db.session.commit()

        print("Demo users, a sample hiring request, and a sample chat are ready.")
        print("Log in as the demo maid or employer and open Messages.")

    # Automatically create missing tables and seed the standard skill list.
    # This prevents "no such table" errors on a fresh local installation.
    with app.app_context():
        db.create_all()
        for skill_name in SKILL_NAMES:
            if not Skill.query.filter_by(name=skill_name).first():
                db.session.add(Skill(name=skill_name))
        db.session.commit()

    return app

app = create_app()
if __name__ == "__main__":
    #app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
    app.run(host="0.0.0.0", port=8080, debug=False )
