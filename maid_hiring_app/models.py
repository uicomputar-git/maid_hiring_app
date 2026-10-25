from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

maid_skills = db.Table(
    "maid_skills",
    db.Column("maid_id", db.Integer, db.ForeignKey("maid_profiles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # maid, employer, admin
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    maid_profile = db.relationship("MaidProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    employer_profile = db.relationship("EmployerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    maids = db.relationship("MaidProfile", secondary=maid_skills, back_populates="skills")

class MaidProfile(db.Model):
    __tablename__ = "maid_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(30), nullable=False, default="Female")
    address = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    state = db.Column(db.String(80), nullable=False)
    photo = db.Column(db.String(255))
    experience_years = db.Column(db.Integer, nullable=False, default=0)
    expected_salary = db.Column(db.Integer, nullable=False)
    working_hours = db.Column(db.String(80), nullable=False)
    job_type = db.Column(db.String(30), nullable=False)
    languages = db.Column(db.String(200), default="")
    available_from = db.Column(db.String(20), default="")
    previous_experience = db.Column(db.Text, default="")
    reference_details = db.Column(db.String(250), default="")
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    consent_public_profile = db.Column(db.Boolean, default=True, nullable=False)
    user = db.relationship("User", back_populates="maid_profile")
    skills = db.relationship("Skill", secondary=maid_skills, back_populates="maids")
    @property
    def average_rating(self):
        ratings = [r.rating for r in Review.query.filter_by(maid_user_id=self.user_id, is_hidden=False).all()]
        return round(sum(ratings) / len(ratings), 1) if ratings else None

class EmployerProfile(db.Model):
    __tablename__ = "employer_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    house_address = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    state = db.Column(db.String(80), nullable=False)
    preferred_maid_type = db.Column(db.String(30), default="Any")
    required_services = db.Column(db.String(300), default="")
    expected_hours = db.Column(db.String(80), default="")
    budget = db.Column(db.Integer, nullable=False)
    preferred_joining_date = db.Column(db.String(20), default="")
    additional_requirements = db.Column(db.Text, default="")
    user = db.relationship("User", back_populates="employer_profile")

class HiringRequest(db.Model):
    __tablename__ = "hiring_requests"
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    maid_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_location = db.Column(db.String(250), nullable=False)
    salary_offered = db.Column(db.Integer, nullable=False)
    work_timings = db.Column(db.String(100), nullable=False)
    job_description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="Pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    employer = db.relationship("User", foreign_keys=[employer_id])
    maid = db.relationship("User", foreign_keys=[maid_id])

class Favourite(db.Model):
    __tablename__ = "favourites"
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    maid_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("employer_id", "maid_id", name="uq_favourite"),)

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    maid_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    hiring_request_id = db.Column(db.Integer, db.ForeignKey("hiring_requests.id"), unique=True, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default="Open", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    hiring_request_id = db.Column(db.Integer, db.ForeignKey("hiring_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = db.Column(db.String(2000), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    sender = db.relationship("User", foreign_keys=[sender_id])
    hiring_request = db.relationship("HiringRequest", foreign_keys=[hiring_request_id])


class DirectConversation(db.Model):
    """One private conversation per unordered pair of users."""
    __tablename__ = "direct_conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_one_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_two_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)
    user_one = db.relationship("User", foreign_keys=[user_one_id])
    user_two = db.relationship("User", foreign_keys=[user_two_id])
    __table_args__ = (UniqueConstraint("user_one_id", "user_two_id", name="uq_direct_conversation_pair"),)

    def other_user(self, user_id):
        return self.user_two if self.user_one_id == user_id else self.user_one


class DirectMessage(db.Model):
    __tablename__ = "direct_messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("direct_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = db.Column(db.String(2000), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    sender = db.relationship("User", foreign_keys=[sender_id])
    conversation = db.relationship("DirectConversation", foreign_keys=[conversation_id])
