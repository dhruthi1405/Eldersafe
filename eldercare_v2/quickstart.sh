#!/bin/bash

# ElderCare AI v2.0 - Quick Start Script
# This script sets up the entire system in one go

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         ElderCare AI v2.0 - Quick Start Setup              ║"
echo "║        Professional Healthcare Monitoring System            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_USER="eldercare_user"
DB_PASSWORD="secure_password_123"
DB_NAME="eldercare_db"

echo -e "${BLUE}Step 1: Checking Prerequisites...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo "  Install Python 3.9+ from https://www.python.org/"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2)${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    echo "  Install Node.js 16+ from https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node --version)${NC}"

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo -e "${RED}✗ PostgreSQL not found${NC}"
    echo "  Install PostgreSQL from https://www.postgresql.org/"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL installed${NC}"

echo ""
echo -e "${BLUE}Step 2: Setting Up Database...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create database and user
echo "Creating database and user..."
sudo -u postgres psql <<EOF || true
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "Importing schema..."
psql -U $DB_USER -d $DB_NAME -f database/schema.sql

echo -e "${GREEN}✓ Database setup complete${NC}"

echo ""
echo -e "${BLUE}Step 3: Setting Up Backend...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate || . venv/Scripts/activate

# Create .env file
echo "Creating .env file..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    sed -i "s/secure_password_here/$DB_PASSWORD/" .env
    echo -e "${YELLOW}✓ .env created - please review and update SECRET_KEY${NC}"
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

echo -e "${GREEN}✓ Backend setup complete${NC}"

cd ..

echo ""
echo -e "${BLUE}Step 4: Setting Up Frontend...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd frontend

# Create .env file
echo "Creating frontend .env file..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ .env created${NC}"
fi

# Install dependencies
echo "Installing npm dependencies..."
npm install -q

echo -e "${GREEN}✓ Frontend setup complete${NC}"

cd ..

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  Setup Complete! 🎉                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo -e "${BLUE}To start the system:${NC}"
echo ""
echo "  Terminal 1 (Backend):"
echo "    cd backend"
echo "    source venv/bin/activate  # or: venv\\Scripts\\activate (Windows)"
echo "    python main.py"
echo ""
echo "  Terminal 2 (Frontend):"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "  Then open: ${YELLOW}http://localhost:5173${NC}"
echo ""
echo -e "${BLUE}Demo Credentials:${NC}"
echo "  Email:    admin@eldercare.com"
echo "  Password: password123"
echo ""
echo -e "${BLUE}Database:${NC}"
echo "  User: $DB_USER"
echo "  Name: $DB_NAME"
echo "  Port: 5432"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  - Setup Guide:  README.md & SETUP.md"
echo "  - API Docs:     http://localhost:8000/docs (when running)"
echo ""
