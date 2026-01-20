#!/bin/bash
# Package script - Run this on your Mac to create deployment package

set -e

echo "=========================================="
echo "Creating Deployment Package"
echo "=========================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Package name
PACKAGE_NAME="monitor_app.tar.gz"

echo "Packaging files..."

# Create the archive
tar -czf "$PACKAGE_NAME" \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='instance' \
  --exclude='*.log' \
  --exclude='*.log.*' \
  --exclude='migrations/versions' \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='monitor_app.tar.gz' \
  app.py \
  wsgi.py \
  gunicorn_config.py \
  requirements.txt \
  templates/ \
  deployment/ \
  deploy.sh \
  .env.example

echo "✓ Package created: $PACKAGE_NAME"
echo ""

# Show package contents
echo "Package contents:"
tar -tzf "$PACKAGE_NAME"
echo ""

# Show package size
PACKAGE_SIZE=$(du -h "$PACKAGE_NAME" | cut -f1)
echo "Package size: $PACKAGE_SIZE"
echo ""

echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Copy package to your Linux server:"
echo "   scp $PACKAGE_NAME username@SERVER_IP:/tmp/"
echo ""
echo "2. SSH into your server:"
echo "   ssh username@SERVER_IP"
echo ""
echo "3. Run the deployment script:"
echo "   cd /tmp"
echo "   tar -xzf monitor_app.tar.gz deploy.sh"
echo "   chmod +x deploy.sh"
echo "   ./deploy.sh"
echo ""
echo "4. Edit .env file with your credentials:"
echo "   nano /opt/client-monitor/.env"
echo ""
echo "5. Restart the service:"
echo "   sudo systemctl restart client-monitor"
echo ""
echo "Done!"
echo ""

