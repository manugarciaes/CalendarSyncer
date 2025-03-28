from datetime import datetime
from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with calendars
    calendars = db.relationship('Calendar', backref='user', lazy=True)
    
    # Relationship with shared links
    shared_links = db.relationship('SharedLink', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Calendar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    outlook_id = db.Column(db.String(256), nullable=False)
    ms_graph_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expiry = db.Column(db.DateTime)
    last_synced = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Calendar {self.name}>'

class SharedLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    link_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    # Store comma-separated list of calendar IDs
    calendar_ids = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_calendar_ids(self):
        """Convert the stored string of calendar IDs to a list of integers"""
        if not self.calendar_ids:
            return []
        return [int(calendar_id) for calendar_id in self.calendar_ids.split(',')]
    
    def set_calendar_ids(self, calendar_ids):
        """Convert a list of calendar IDs to a comma-separated string"""
        self.calendar_ids = ','.join(str(calendar_id) for calendar_id in calendar_ids)
    
    def __repr__(self):
        return f'<SharedLink {self.name}>'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shared_link_id = db.Column(db.Integer, db.ForeignKey('shared_link.id'), nullable=False)
    customer_name = db.Column(db.String(128), nullable=False)
    customer_email = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    outlook_event_ids = db.Column(db.Text)  # Store comma-separated list of event IDs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    shared_link = db.relationship('SharedLink', backref='bookings')
    
    def __repr__(self):
        return f'<Booking {self.subject} at {self.start_time}>'
