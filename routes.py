import os
import logging
import uuid
from datetime import datetime, timedelta
import pytz
import re
from flask import render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from models import User, Calendar, SharedLink, Booking
from auth import register_user, login_user
from calendar_sync import (
    get_calendar_events, get_free_slots, create_booking, 
    get_booking_analytics, get_calendar_analytics,
    refresh_calendar_events, start_scheduler, update_calendar_refresh_interval
)

def init_routes(app):
    @app.route('/')
    def index():
        """Home page with app description and login/register options"""
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('index.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Register a new user"""
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not username or not email or not password:
                flash('All fields are required', 'danger')
                return render_template('login.html', register=True)
            
            user, error = register_user(username, email, password)
            if user:
                flash('Registration successful! Please log in', 'success')
                return redirect(url_for('login'))
            else:
                flash(f'Registration failed: {error}', 'danger')
                return render_template('login.html', register=True)
        
        return render_template('login.html', register=True)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login an existing user"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not username or not password:
                flash('Username and password are required', 'danger')
                return render_template('login.html')
            
            user, error = login_user(username, password)
            if user:
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash(f'Login failed: {error}', 'danger')
                return render_template('login.html')
        
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        """Log out the current user"""
        session.clear()
        flash('You have been logged out', 'info')
        return redirect(url_for('index'))

    @app.route('/dashboard')
    def dashboard():
        """Dashboard for managing calendars and shared links"""
        if 'user_id' not in session:
            flash('Please log in to access the dashboard', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        calendars = Calendar.query.filter_by(user_id=user_id).all()
        shared_links = SharedLink.query.filter_by(user_id=user_id).all()
        
        return render_template('dashboard.html', 
                              calendars=calendars, 
                              shared_links=shared_links)

    @app.route('/add_calendar', methods=['GET', 'POST'])
    def add_calendar():
        """Add a new calendar using ICS URL"""
        if 'user_id' not in session:
            flash('Please log in to add a calendar', 'warning')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            user_id = session['user_id']
            calendar_name = request.form.get('calendar_name')
            ics_url = request.form.get('ics_url')
            refresh_interval = request.form.get('refresh_interval', 60)
            
            # Validate inputs
            if not calendar_name or not ics_url:
                flash('Calendar name and ICS URL are required', 'danger')
                return render_template('add_calendar.html')
            
            try:
                # Validate the refresh interval is a positive integer
                refresh_interval = int(refresh_interval)
                if refresh_interval < 1:
                    refresh_interval = 60  # Default to 60 minutes if invalid
            except ValueError:
                refresh_interval = 60  # Default to 60 minutes if not a valid integer
            
            # Validate URL format
            if not re.match(r'^https?://', ics_url):
                flash('ICS URL must be a valid HTTP or HTTPS URL', 'danger')
                return render_template('add_calendar.html')
            
            try:
                # Create the calendar record
                calendar = Calendar(
                    user_id=user_id,
                    name=calendar_name,
                    ics_url=ics_url,
                    calendar_type='ics',
                    refresh_interval=refresh_interval,
                    active=True,
                    created_at=datetime.now()
                )
                db.session.add(calendar)
                db.session.flush()  # Get the ID without committing
                
                # Try to fetch the calendar events to validate the URL
                events = refresh_calendar_events(calendar)
                if events is None:
                    db.session.rollback()
                    flash('Failed to fetch events from the provided ICS URL. Please check the URL and try again.', 'danger')
                    return render_template('add_calendar.html')
                
                # If we got here, the URL is valid
                db.session.commit()
                
                # Schedule the refresh job for this calendar
                start_scheduler()  # This will start the scheduler if it's not already running
                
                flash(f'Calendar "{calendar_name}" added successfully', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error adding calendar: {e}")
                flash('An error occurred while adding the calendar', 'danger')
                return render_template('add_calendar.html')
        
        return render_template('add_calendar.html')

    @app.route('/update_calendar_refresh/<int:calendar_id>', methods=['POST'])
    def update_calendar_refresh(calendar_id):
        """Update the refresh interval for a calendar"""
        if 'user_id' not in session:
            flash('Please log in to update calendar settings', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        refresh_interval = request.form.get('refresh_interval', 60)
        
        # Validate inputs
        try:
            refresh_interval = int(refresh_interval)
            if refresh_interval < 1:
                refresh_interval = 60  # Default to 60 minutes if invalid
        except ValueError:
            refresh_interval = 60  # Default to 60 minutes if not a valid integer
        
        # Update the calendar refresh interval
        success, error = update_calendar_refresh_interval(calendar_id, refresh_interval)
        
        if success:
            flash(f'Calendar refresh interval updated to {refresh_interval} minutes', 'success')
        else:
            flash(f'Failed to update calendar refresh interval: {error}', 'danger')
        
        return redirect(url_for('dashboard'))

    @app.route('/create_shared_link', methods=['POST'])
    def create_shared_link():
        """Create a new shared link for selected calendars"""
        if 'user_id' not in session:
            flash('Please log in to create a shared link', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        name = request.form.get('name')
        description = request.form.get('description', '')
        calendar_ids = request.form.getlist('calendar_ids')
        
        if not name or not calendar_ids:
            flash('Name and at least one calendar are required', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            # Create a unique link ID
            link_id = str(uuid.uuid4()).replace('-', '')[:16]
            
            # Create the shared link
            shared_link = SharedLink(
                user_id=user_id,
                link_id=link_id,
                name=name,
                description=description,
                calendar_ids=','.join(calendar_ids)
            )
            
            db.session.add(shared_link)
            db.session.commit()
            
            flash('Shared link created successfully', 'success')
            return redirect(url_for('dashboard'))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating shared link: {e}")
            flash('Failed to create shared link', 'danger')
            return redirect(url_for('dashboard'))

    @app.route('/shared/<link_id>')
    def customer_view(link_id):
        """Public view for customers to see available slots and book appointments"""
        shared_link = SharedLink.query.filter_by(link_id=link_id).first()
        
        if not shared_link or not shared_link.active:
            abort(404)
        
        # Get the calendar IDs from the shared link
        calendar_ids = shared_link.get_calendar_ids()
        calendars = Calendar.query.filter(Calendar.id.in_(calendar_ids)).all()
        
        if not calendars:
            flash('No calendars found for this link', 'warning')
            return render_template('customer_view.html', shared_link=shared_link, slots=[])
        
        # Default to searching for slots in the next 7 days
        start_date = datetime.now(pytz.utc)
        end_date = start_date + timedelta(days=7)
        
        # Get free slots across all calendars
        free_slots = get_free_slots(calendars, start_date, end_date)
        
        return render_template('customer_view.html', 
                              shared_link=shared_link, 
                              slots=free_slots,
                              start_date=start_date,
                              end_date=end_date)

    @app.route('/api/slots', methods=['GET'])
    def get_slots_api():
        """API endpoint to get available slots for a shared link"""
        link_id = request.args.get('link_id')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not link_id:
            return jsonify({'error': 'Missing link_id parameter'}), 400
        
        shared_link = SharedLink.query.filter_by(link_id=link_id).first()
        if not shared_link or not shared_link.active:
            return jsonify({'error': 'Shared link not found or inactive'}), 404
        
        # Parse dates or use defaults
        try:
            start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now(pytz.utc)
            end_date = datetime.fromisoformat(end_date_str) if end_date_str else start_date + timedelta(days=7)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Get the calendar IDs from the shared link
        calendar_ids = shared_link.get_calendar_ids()
        calendars = Calendar.query.filter(Calendar.id.in_(calendar_ids)).all()
        
        if not calendars:
            return jsonify({'error': 'No calendars found for this link'}), 404
        
        # Get free slots across all calendars
        free_slots = get_free_slots(calendars, start_date, end_date)
        
        return jsonify({'slots': free_slots})

    @app.route('/book', methods=['POST'])
    def book_appointment():
        """Book an appointment in the selected slot"""
        link_id = request.form.get('link_id')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        customer_name = request.form.get('customer_name')
        customer_email = request.form.get('customer_email')
        subject = request.form.get('subject')
        description = request.form.get('description', '')
        
        if not all([link_id, start_time_str, end_time_str, customer_name, customer_email, subject]):
            flash('All fields are required', 'danger')
            return redirect(url_for('customer_view', link_id=link_id))
        
        shared_link = SharedLink.query.filter_by(link_id=link_id).first()
        if not shared_link or not shared_link.active:
            flash('Shared link not found or inactive', 'danger')
            return redirect(url_for('index'))
        
        try:
            # Parse the date strings
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            
            # Create the booking
            booking, error = create_booking(
                shared_link_id=shared_link.id,
                customer_name=customer_name,
                customer_email=customer_email,
                start_time=start_time,
                end_time=end_time,
                subject=subject,
                description=description
            )
            
            if booking:
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('booking_success', booking_id=booking.id))
            else:
                flash(f'Failed to book appointment: {error}', 'danger')
                return redirect(url_for('customer_view', link_id=link_id))
            
        except Exception as e:
            logging.error(f"Error booking appointment: {e}")
            flash('An error occurred while booking the appointment', 'danger')
            return redirect(url_for('customer_view', link_id=link_id))

    @app.route('/success/<int:booking_id>')
    def booking_success(booking_id):
        """Success page after booking an appointment"""
        booking = Booking.query.get(booking_id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('index'))
        
        shared_link = SharedLink.query.get(booking.shared_link_id)
        if not shared_link:
            flash('Shared link not found', 'danger')
            return redirect(url_for('index'))
        
        return render_template('success.html', booking=booking, shared_link=shared_link)

    @app.route('/delete_calendar/<int:calendar_id>', methods=['POST'])
    def delete_calendar(calendar_id):
        """Delete a calendar"""
        if 'user_id' not in session:
            flash('Please log in to delete a calendar', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        calendar = Calendar.query.filter_by(id=calendar_id, user_id=user_id).first()
        
        if not calendar:
            flash('Calendar not found or you do not have permission to delete it', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            # Mark as inactive instead of deleting
            calendar.active = False
            db.session.commit()
            flash('Calendar removed successfully', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting calendar: {e}")
            flash('Failed to remove calendar', 'danger')
        
        return redirect(url_for('dashboard'))

    @app.route('/delete_shared_link/<int:link_id>', methods=['POST'])
    def delete_shared_link(link_id):
        """Delete a shared link"""
        if 'user_id' not in session:
            flash('Please log in to delete a shared link', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        shared_link = SharedLink.query.filter_by(id=link_id, user_id=user_id).first()
        
        if not shared_link:
            flash('Shared link not found or you do not have permission to delete it', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            # Mark as inactive instead of deleting
            shared_link.active = False
            db.session.commit()
            flash('Shared link removed successfully', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting shared link: {e}")
            flash('Failed to remove shared link', 'danger')
        
        return redirect(url_for('dashboard'))
        
    @app.route('/analytics')
    def analytics():
        """Calendar analytics dashboard"""
        if 'user_id' not in session:
            flash('Please log in to view analytics', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        
        # Get date range from query parameters or use defaults
        try:
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str)
            else:
                # Default to last 30 days
                start_date = datetime.now() - timedelta(days=30)
                
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str)
            else:
                # Default to current date
                end_date = datetime.now()
        except ValueError as e:
            flash('Invalid date format. Using default range (last 30 days).', 'warning')
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now()
        
        # Get analytics data
        calendar_id = request.args.get('calendar_id')
        if calendar_id:
            try:
                calendar_id = int(calendar_id)
                calendar = Calendar.query.filter_by(id=calendar_id, user_id=user_id).first()
                if not calendar:
                    calendar_id = None  # Reset if invalid calendar ID
            except ValueError:
                calendar_id = None
        
        # Query user's calendars for the filter dropdown
        calendars = Calendar.query.filter_by(user_id=user_id, active=True).all()
        
        # Get analytics data
        booking_analytics = get_booking_analytics(user_id, start_date, end_date)
        calendar_analytics = get_calendar_analytics(user_id, calendar_id, start_date, end_date)
        
        return render_template('analytics.html',
                              booking_analytics=booking_analytics,
                              calendar_analytics=calendar_analytics,
                              calendars=calendars,
                              selected_calendar_id=calendar_id,
                              start_date=start_date,
                              end_date=end_date)
    
    @app.route('/api/analytics/booking', methods=['GET'])
    def booking_analytics_api():
        """API endpoint for booking analytics data"""
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        
        # Get date range from query parameters
        try:
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str)
            else:
                start_date = None
                
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str)
            else:
                end_date = None
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Get analytics data
        analytics_data = get_booking_analytics(user_id, start_date, end_date)
        if analytics_data is None:
            return jsonify({'error': 'Failed to generate analytics'}), 500
        
        return jsonify(analytics_data)
    
    @app.route('/api/analytics/calendar', methods=['GET'])
    def calendar_analytics_api():
        """API endpoint for calendar analytics data"""
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        
        # Get date range and calendar ID from query parameters
        try:
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            calendar_id_str = request.args.get('calendar_id')
            
            start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
            end_date = datetime.fromisoformat(end_date_str) if end_date_str else None
            calendar_id = int(calendar_id_str) if calendar_id_str else None
            
            # Verify calendar belongs to user if ID is specified
            if calendar_id:
                calendar = Calendar.query.filter_by(id=calendar_id, user_id=user_id).first()
                if not calendar:
                    return jsonify({'error': 'Calendar not found or access denied'}), 404
        except ValueError:
            return jsonify({'error': 'Invalid parameters'}), 400
        
        # Get analytics data
        analytics_data = get_calendar_analytics(user_id, calendar_id, start_date, end_date)
        if analytics_data is None:
            return jsonify({'error': 'Failed to generate analytics'}), 500
        
        return jsonify(analytics_data)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500
