# Installation Guide - Text2SQL Analytics System

Complete installation and setup guide for the Text2SQL Analytics System.

## Prerequisites

### Required Software
- **Python 3.10+**: [Download](https://www.python.org/downloads/)
- **PostgreSQL 14+**: [Download](https://www.postgresql.org/download/) OR Docker
- **Git**: [Download](https://git-scm.com/downloads)

### Required Accounts
- **Google Gemini API Key**: [Get Free Key](https://ai.google.dev/)

## Installation Methods

### Method 1: Automated Setup (Recommended)

```bash
# Clone repository
git clone <your-repo-url>
cd text2sql-analytics

# Run automated setup
./GET_STARTED.sh

# Follow the prompts to configure .env
# Then continue with:
make setup
```

### Method 2: Manual Setup

#### Step 1: Environment Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Configuration

```bash
# Copy environment template
cp env.example .env

# Edit .env file with your credentials
nano .env  # or use any text editor
```

Required configurations in `.env`:
```env
# Get from https://ai.google.dev/
GEMINI_API_KEY=AIza...your-key-here

# PostgreSQL admin credentials
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=your-postgres-password

# Database connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=northwind
```

#### Step 3: Database Setup (Choose One)

**Option A: Using Docker (Easier)**

```bash
# Start PostgreSQL container
docker-compose up -d

# Wait for PostgreSQL to start (10 seconds)
sleep 10

# Verify it's running
docker ps
```

**Option B: Local PostgreSQL**

```bash
# macOS (with Homebrew)
brew install postgresql@14
brew services start postgresql@14

# Ubuntu/Debian
sudo apt-get install postgresql-14
sudo service postgresql start

# Windows
# Download and install from postgresql.org
# Start PostgreSQL service
```

Verify PostgreSQL is running:
```bash
psql -U postgres -c "SELECT version();"
```

#### Step 4: Prepare Northwind Data

The repository ships with cleaned CSV exports under `data/raw/northwind/`.  
If you replace them, keep one CSV per table (e.g. `categories.csv`, `orders.csv`).  
The setup script automatically maps the CSV headers to the ready-made schema in `data/schema/schema.sql`.

#### Step 5: Initialize Database

```bash
# Create database, schema, and load data
python scripts/setup_database.py
```

This will:
1. Create `northwind` database (if needed)
2. Execute the curated schema from `data/schema/schema.sql`
3. Load the CSVs from `data/raw/northwind/`
4. Load optional custom data (e.g. `data/raw/result/Result.csv`)
5. Verify row counts table-by-table

Expected output:
```
Creating database...
  ✓ Database 'northwind' created
Creating database schema...
  ✓ Schema created successfully
Loading and normalizing data...
  ✓ Loaded 77 rows into categories
  ✓ Loaded 29 rows into suppliers
  ...
✓ Database setup verified successfully!
```

#### Step 6: Verify Installation

```bash
# Run verification script
python scripts/verify_setup.py
```

All checks should pass:
```
✓ PASS   Python Version
✓ PASS   Dependencies
✓ PASS   Environment Variables
✓ PASS   Project Structure
✓ PASS   Data File
✓ PASS   Database Connection
✓ PASS   Database Schema
✓ PASS   Gemini API
```

## Testing Installation

### Run Test Suite

```bash
# Run all tests
pytest tests/ -v

# Expected output:
# tests/test_query_validator.py ✓✓✓✓✓... 
# tests/test_database.py ✓✓✓✓...
# tests/test_accuracy/... ✓✓✓...
# 
# ========== XX passed in X.XXs ==========
```

### Check Code Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

Target: **80%+ coverage** ✅

### Run Evaluation

```bash
# Evaluate on all 20 test questions
python scripts/run_evaluation.py

# Check results
cat evaluation_results.json
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution:**
```bash
# Make sure you're in the project root directory
cd text2sql-analytics

# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall in development mode
pip install -e .
```

### Issue: "Database connection failed"

**Solutions:**
1. Check PostgreSQL is running:
   ```bash
   # Docker
   docker ps | grep northwind_db
   
   # Local
   psql -U postgres -c "SELECT 1"
   ```

2. Verify credentials in `.env`:
   ```bash
   cat .env | grep DB_
   ```

3. Check PostgreSQL logs:
   ```bash
   # Docker
   docker logs northwind_db
   
   # Local (Ubuntu)
   sudo tail -f /var/log/postgresql/postgresql-14-main.log
   ```

### Issue: "Gemini API key not found"

**Solution:**
1. Get API key: https://ai.google.dev/
2. Add to `.env`:
   ```env
   GEMINI_API_KEY=your_actual_key_here
   ```
3. Restart application

### Issue: "Table 'products' does not exist"

**Solution:**
```bash
# Re-run database setup
python scripts/setup_database.py

# Verify tables exist
psql -U postgres -d northwind -c "\dt"
```

### Issue: "pytest: command not found"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Permission denied" errors

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.py
chmod +x GET_STARTED.sh

# Or run with python directly
python scripts/setup_database.py
```

## Platform-Specific Notes

### macOS
- Use Homebrew for PostgreSQL: `brew install postgresql@14`
- Default PostgreSQL user: your system username
- Check with: `psql postgres`

### Linux (Ubuntu/Debian)
- Install: `sudo apt-get install postgresql-14 python3.10`
- Start service: `sudo service postgresql start`
- Default user: `postgres`

### Windows
- Use PostgreSQL installer from postgresql.org
- Add PostgreSQL bin to PATH
- Use PowerShell or Git Bash for commands

## Docker Setup (Detailed)

### Install Docker

- **macOS**: [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- **Windows**: [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

### Start Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f postgres

# Stop services
docker-compose down

# Stop and remove data
docker-compose down -v
```

## Verification Checklist

Before proceeding, ensure:

- [ ] Python 3.10+ installed and in PATH
- [ ] PostgreSQL 14+ running (or Docker)
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip list`)
- [ ] `.env` file configured with actual credentials
- [ ] Database created and schema loaded
- [ ] Northwind data file downloaded
- [ ] Verification script passes all checks
- [ ] Test suite runs successfully

## Getting Help

If you encounter issues:

1. **Check logs**: `tail -f text2sql.log`
2. **Run verification**: `python scripts/verify_setup.py`
3. **Check environment**: `python -c "from src.config import settings; print(settings)"`
4. **Test database**: `psql -U postgres -d northwind -c "SELECT COUNT(*) FROM products;"`

## Next Steps

After successful installation:

1. **Read QUICKSTART.md** for a 5-minute intro
2. **Run evaluation**: `make evaluate`
3. **Try interactive mode**: `python -m src.cli`
4. **Explore notebook**: `jupyter notebook notebooks/analysis.ipynb`
5. **Read full documentation**: `README.md`

---

**Installation Support**: asifsadek509@gmail.com
