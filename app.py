import os
import logging
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_session import Session

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create a base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)

# Configure the secret key
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure session type
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True

# Configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///calendar_sync.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
Session(app)

# Add utility functions to Jinja environment
@app.context_processor
def utility_processor():
    return dict(now=datetime.now)

# Load configuration from config.py
from config import MS_GRAPH_CLIENT_ID, MS_GRAPH_AUTHORITY, MS_GRAPH_SCOPES

# Create database tables
with app.app_context():
    # Import models here to avoid circular imports
    import models
    db.create_all()

# Import and register routes
from routes import init_routes
init_routes(app)

# Log that the application is ready
logging.debug("Application initialized and ready to serve requests")
