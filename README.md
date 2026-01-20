# Client Health Monitoring System

A Flask-based web application for monitoring network client health status in real-time. Tracks ping connectivity, SSH availability, and WiFi agent API status with automated email alerts.

## Features

- 🔍 **Real-time Monitoring** - Checks client status every 30 seconds
- 📊 **Multi-Service Tracking** - Monitors Ping (ICMP), SSH (Port 22), and WiFi Agent API (Port 8083)
- 📧 **Email Alerts** - Automated notifications when services go offline
- 🔄 **Auto-Refresh UI** - Live dashboard updates every 30 seconds
- ⚡ **Rate Limiting** - Built-in protection against abuse
- 🎨 **Responsive Design** - Bootstrap 5 UI works on all devices

## Tech Stack

**Backend:**
- Python 3.12+
- Flask 3.1.2
- SQLAlchemy (ORM)
- APScheduler (Background jobs)
- Gunicorn (WSGI server)

**Frontend:**
- HTML5, CSS3, JavaScript (ES6)
- Bootstrap 5.3.0
- Fetch API for AJAX

**Database:**
- SQLite 3

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Linux server (for production deployment)
- Gmail account (for email alerts)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd monitor_project_flask
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Update with your settings:
   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SENDER_EMAIL=your-email@gmail.com
   SENDER_PASSWORD=your-app-password
   SECRET_KEY=your-secret-key
   ALERT_COOLDOWN_SECONDS=3600
   ```

5. **Initialize database:**
   ```bash
   python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

6. **Run development server:**
   ```bash
   python3 app.py
   ```

7. **Access the application:**
   ```
   http://localhost:5001
   ```

## Production Deployment

### Using the Automated Deployment Script

1. **On your Mac - Create deployment package:**
   ```bash
   ./package.sh
   ```

2. **Copy to server:**
   ```bash
   scp monitor_app.tar.gz username@SERVER_IP:/tmp/
   ```

3. **On server - Deploy:**
   ```bash
   ssh username@SERVER_IP
   cd /tmp
   tar -xzf monitor_app.tar.gz deploy.sh
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Configure environment:**
   ```bash
   sudo nano /opt/client-monitor/.env
   ```

5. **Start service:**
   ```bash
   sudo systemctl start client-monitor
   sudo systemctl enable client-monitor
   ```
6. **Logs:**
```bash
sudo journalctl -u client-monitor -f
```

### Manual Deployment

See `deploy.sh` for detailed deployment steps.

## Usage

1. **Add a client:**
   - Enter IP address (e.g., 192.168.1.100)
   - Enter alert email
   - Click "Add"

2. **Monitor status:**
   - Dashboard shows real-time status
   - Green = Online, Red = Offline
   - Auto-refreshes every 30 seconds

3. **Receive alerts:**
   - Email sent when service goes offline
   - Alert cooldown: 60 minutes
   - Alerts continue until service restored

## API Endpoints

- `GET /` - Main dashboard
- `GET /health` - Health check endpoint
- `GET /api/clients` - Get all clients (JSON)
- `POST /add_client` - Add new client
- `POST /delete_client/<id>` - Remove client

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_SERVER` | SMTP server address | smtp.gmail.com |
| `SMTP_PORT` | SMTP server port | 587 |
| `SENDER_EMAIL` | Email address for alerts | - |
| `SENDER_PASSWORD` | Email app password | - |
| `SECRET_KEY` | Flask secret key | - |
| `ALERT_COOLDOWN_SECONDS` | Time between alerts | 3600 |

### Rate Limits

- Default: 1000 requests/hour per IP
- Add client: 10 requests/minute
- Delete client: 20 requests/minute

## Project Structure

```
monitor_project_flask/
├── app.py                          # Main Flask application
├── wsgi.py                         # WSGI entry point
├── gunicorn_config.py              # Gunicorn configuration
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── package.sh                      # Create deployment package
├── deploy.sh                       # Deployment script
├── templates/
│   └── index.html                  # Frontend template
└── deployment/
    └── client-monitor.service      # Systemd service file
```

## License

MIT License - feel free to use for your projects!

## Author

Siddharth Patel

## Support

For issues or questions, please open an issue on GitHub.

