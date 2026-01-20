import platform
import subprocess
import socket
import requests
import smtplib
import os
import ipaddress
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from email.mime.text import MIMEText
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Logging Configuration ---
# Use RotatingFileHandler to prevent log file from growing indefinitely
file_handler = RotatingFileHandler(
    'app.log',
    maxBytes=10485760,  # 10MB
    backupCount=10
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure our logger is also DEBUG

app = Flask(__name__)

# --- Configuration ---
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_for_flash_messages')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_API_ENABLED'] = True

# --- Email Config (Loaded from .env file) ---
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')

# Alert Cooldown (1 Hour)
ALERT_COOLDOWN_SECONDS = int(os.getenv('ALERT_COOLDOWN_SECONDS', 3600))

db = SQLAlchemy(app)
migrate = Migrate(app, db)
scheduler = APScheduler()

# Initialize rate limiter
# For internal team use: 45 users × 180 req/hour = 8100 total, but limit is per-IP
# Each user needs ~200 req/hour for auto-refresh, so 1000/hour gives plenty of headroom
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10000 per day", "1000 per hour"],  # Generous limits for internal team use
    storage_uri="memory://"
)

# --- Database Model ---
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # 1. REMOVED unique=True from ip_address to allow multiple users to track same IP
    ip_address = db.Column(db.String(50), nullable=False) 
    alert_email = db.Column(db.String(120), nullable=False)
    
    # Statuses
    ping_status = db.Column(db.String(20), default='Pending')
    ssh_status = db.Column(db.String(20), default='Pending')
    wifi_status = db.Column(db.String(20), default='Pending')
    
    last_updated = db.Column(db.DateTime, default=datetime.now)
    last_alert_sent = db.Column(db.DateTime, nullable=True)

    # 2. ADDED Composite Unique Constraint
    # This ensures (IP + Email) pair is unique, but IP itself can be repeated.
    __table_args__ = (db.UniqueConstraint('ip_address', 'alert_email', name='_user_client_uc'),)

# --- Helper Functions ---

def validate_ip_address(ip_string):
    """
    Validates if the given string is a valid IPv4 or IPv6 address.
    Returns tuple: (is_valid: bool, error_message: str or None)
    """
    if not ip_string or not ip_string.strip():
        return False, "IP address cannot be empty"

    ip_string = ip_string.strip()

    try:
        # This will raise ValueError if invalid
        ipaddress.ip_address(ip_string)
        return True, None
    except ValueError:
        return False, f"Invalid IP address format: '{ip_string}'"

def validate_email_address(email_string):
    """
    Validates email address using email-validator library.
    Returns tuple: (is_valid: bool, error_message: str or None)
    """
    if not email_string or not email_string.strip():
        return False, "Email address cannot be empty"

    email_string = email_string.strip()

    try:
        # Validate and get normalized email
        valid = validate_email(email_string, check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)

def check_ping(ip):
    """Checks ping with a strict 1-second timeout."""
    system_os = platform.system().lower()
    if system_os == 'windows':
        command = ['ping', '-n', '1', '-w', '1000', ip]
    else:
        # Use full path to ping binary to avoid PATH issues
        command = ['/bin/ping', '-c', '1', '-W', '1', ip]

    try:
        result = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        success = result == 0
        if not success:
            logger.debug(f"Ping failed for {ip} - return code: {result}")
        return success
    except Exception as e:
        logger.error(f"Ping exception for {ip}: {str(e)}")
        return False

def check_ssh(ip):
    """Checks port 22 with a 2-second timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2) 
    try:
        result = sock.connect_ex((ip, 22))
        sock.close()
        return result == 0
    except Exception:
        return False

def check_wifi_agent(ip):
    """Checks the API with a 3-second timeout."""
    url = f"http://{ip}:8083/device/traffic/browsing/profile/get"
    try:
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False

def send_alert(client_ip, recipient, issue_list):
    subject = f"Client-Health: Services Down for {client_ip}"
    
    formatted_issues = ""
    for index, issue in enumerate(issue_list, 1):
        formatted_issues += f"{index}. {issue}\n"

    footer = (
        "----------------------------------------\n"
        "This is an automated email to report client health issues, "
        "take appropriate action to avoid getting this message every hour."
    )
    
    # Zero-width space trick
    display_ip = client_ip.replace('.', '.\u200B')

    body = (
        f"The following services are down for client {display_ip}:\n\n"
        f"{formatted_issues}\n"
        f"{footer}"
    )
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient

    try:
        # --- SENDING LOGIC ---
        # Uncomment below for real emails
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {recipient} | Subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {e}", exc_info=True)

# --- Background Task ---

def update_statuses():
    """Runs every 30s. Checks every row independently."""
    with app.app_context():
        clients = Client.query.all()
        logger.info(f"Running status check for {len(clients)} client(s)")
        
        for client in clients:
            try:
                # Perform Checks
                # Note: If two users track the same IP, we check it twice.
                # This is actually GOOD because it keeps their 'last_updated' times independent.
                logger.debug(f"Checking client: {client.ip_address}")
                is_ping_up = check_ping(client.ip_address)
                is_ssh_up = check_ssh(client.ip_address)
                is_wifi_up = check_wifi_agent(client.ip_address)

                client.ping_status = 'Online' if is_ping_up else 'Offline'
                client.ssh_status = 'Online' if is_ssh_up else 'Offline'
                client.wifi_status = 'Online' if is_wifi_up else 'Offline'
                client.last_updated = datetime.now()

                logger.debug(f"  {client.ip_address} - Ping: {client.ping_status}, SSH: {client.ssh_status}, WiFi: {client.wifi_status}")

                issues = []
                if not is_ping_up: issues.append("Ping Unreachable")
                if not is_ssh_up: issues.append("SSH Port 22 Closed")
                if not is_wifi_up: issues.append("WifiAgent API Unreachable")

                # Alert Logic (Independent per user)
                if issues:
                    if client.last_alert_sent:
                        time_since = (datetime.now() - client.last_alert_sent).total_seconds()
                    else:
                        time_since = ALERT_COOLDOWN_SECONDS + 1

                    if time_since > ALERT_COOLDOWN_SECONDS:
                        logger.warning(f"Sending alert for {client.ip_address} to {client.alert_email} - Issues: {', '.join(issues)}")
                        send_alert(client.ip_address, client.alert_email, issues)
                        client.last_alert_sent = datetime.now()
                    else:
                        logger.debug(f"Alert cooldown active for {client.ip_address} ({int(time_since)}s since last alert)")
                else:
                    # Client is healthy, reset alert timestamp
                    if client.last_alert_sent:
                        logger.info(f"Client {client.ip_address} is now healthy, resetting alert timestamp")
                    client.last_alert_sent = None

            except Exception as e:
                logger.error(f"Error checking client {client.ip_address}: {e}", exc_info=True)
                continue

        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Database commit failed during status update: {e}", exc_info=True)
            db.session.rollback()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    Returns JSON with application health status.
    """
    try:
        # Check database connectivity
        db_healthy = False
        client_count = 0
        try:
            client_count = Client.query.count()
            db_healthy = True
        except Exception as db_error:
            logger.error(f"Database health check failed: {str(db_error)}")

        # Check scheduler status
        scheduler_running = scheduler.running if scheduler else False

        # Overall health status
        healthy = db_healthy
        status_code = 200 if healthy else 503

        health_data = {
            'status': 'healthy' if healthy else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'database': {
                    'status': 'up' if db_healthy else 'down',
                    'client_count': client_count
                },
                'scheduler': {
                    'status': 'running' if scheduler_running else 'stopped'
                }
            },
            'version': '1.0.0',
            'uptime': 'running'
        }

        return jsonify(health_data), status_code

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.route('/api/clients', methods=['GET'])
def get_clients():
    clients = Client.query.all()
    data = []
    current_time = datetime.now()
    
    for c in clients:
        alert_active = False
        if c.last_alert_sent:
            time_since = (current_time - c.last_alert_sent).total_seconds()
            if time_since < ALERT_COOLDOWN_SECONDS:
                alert_active = True

        data.append({
            'id': c.id,
            'ip': c.ip_address,
            'email': c.alert_email,
            'ping': c.ping_status,
            'ssh': c.ssh_status,
            'wifi': c.wifi_status,
            'last_updated': c.last_updated.strftime("%H:%M:%S"),
            'alert_active': alert_active
        })
    return jsonify(data)

@app.route('/add_client', methods=['POST'])
@limiter.limit("10 per minute")
def add_client():
    ip = request.form.get('ip_address', '').strip()
    email = request.form.get('alert_email', '').strip()

    # Validate inputs
    if not ip or not email:
        logger.warning(f"Add client attempt with missing fields - IP: '{ip}', Email: '{email}'")
        flash('Both IP address and email are required', 'error')
        return redirect(url_for('index'))

    # Validate IP address format
    is_valid, error_msg = validate_ip_address(ip)
    if not is_valid:
        logger.warning(f"Invalid IP address format attempted: '{ip}'")
        flash(error_msg, 'error')
        return redirect(url_for('index'))

    # Validate email using email-validator library
    is_valid_email, email_error = validate_email_address(email)
    if not is_valid_email:
        logger.warning(f"Invalid email format attempted: '{email}' - {email_error}")
        flash(f"Invalid email: {email_error}", 'error')
        return redirect(url_for('index'))

    try:
        # Check if this specific pair (IP + Email) already exists
        existing = Client.query.filter_by(ip_address=ip, alert_email=email).first()

        if existing:
            logger.info(f"Duplicate client add attempt - IP: {ip}, Email: {email}")
            flash(f"Client {ip} with email {email} already exists", 'warning')
        else:
            new_client = Client(ip_address=ip, alert_email=email)
            db.session.add(new_client)
            db.session.commit()
            logger.info(f"Successfully added new client - IP: {ip}, Email: {email}")
            flash(f"Successfully added client {ip}", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding client: {str(e)}", 'error')
        logger.error(f"Database error in add_client for IP {ip}: {e}", exc_info=True)

    return redirect(url_for('index'))

@app.route('/delete_client/<int:id>', methods=['POST'])
@limiter.limit("20 per minute")
def delete_client(id):
    try:
        client = Client.query.get(id)
        if client:
            ip = client.ip_address
            email = client.alert_email
            db.session.delete(client)
            db.session.commit()
            logger.info(f"Deleted client - ID: {id}, IP: {ip}, Email: {email}")
            flash(f"Successfully deleted client {ip}", 'success')
        else:
            logger.warning(f"Attempted to delete non-existent client ID: {id}")
            flash(f"Client not found", 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting client ID {id}: {e}", exc_info=True)
        flash(f"Error deleting client: {str(e)}", 'error')

    return redirect(url_for('index'))

# Initialize scheduler at module level (works with both Flask dev server and Gunicorn)
def init_scheduler():
    """Initialize and start the scheduler."""
    if not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()
        logger.info("Scheduler started")

        # Add the status check job
        try:
            app.apscheduler.add_job(
                func=update_statuses,
                trigger='interval',
                seconds=30,
                id='status_check_job',
                replace_existing=True
            )
            logger.info("Status check job scheduled (every 30 seconds)")
        except Exception as e:
            logger.error(f"Error scheduling job: {str(e)}")

# Initialize database and scheduler when module is loaded
with app.app_context():
    db.create_all()
    logger.info("Database initialized")

# Start scheduler
init_scheduler()

if __name__ == '__main__':
    logger.info("Starting Flask Client Monitor Application")
    logger.info("Starting Flask server on port 5001")
    app.run(debug=True, port=5001)