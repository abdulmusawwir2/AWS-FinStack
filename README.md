# AWS FinStack — Smart Expense Tracker

> A full-stack cloud-native expense tracking dashboard built with
> **Python Flask**, **Vanilla JavaScript**, **AWS DynamoDB**, and **AWS SNS**.
> Designed as a final-year project combining full-stack development, cloud computing, analytics, and real-time dashboarding.

---

## ✨ Features

### 👤 User Authentication
- User registration & login with bcrypt password hashing
- Session-based secure access (`login_required` decorator)
- Per-user data isolation in DynamoDB

### 📊 Dashboard Overview
- Total spending summary (all-time)
- Monthly expenditure tracking
- Spending trend — up / down / stable vs. previous month
- Month-end spending forecast (daily burn rate projection)

### 💳 Transaction Management
- Add, edit, delete transactions
- View full transaction history
- Notes support on every transaction

### 🗂️ Category-Based Expense Tracking
12 built-in categories:
`Food & Dining` · `Transportation` · `Shopping` · `Entertainment` · `Health & Medical` · `Housing & Rent` · `Utilities` · `Education` · `Travel` · `Personal Care` · `Subscriptions` · `Other`

### 🎯 Budget Management
- Set a monthly budget per user
- Budget **persisted in DynamoDB** (survives logout & server restarts)
- Budget utilization progress bar (safe / warning / danger)
- Compare spending vs. budget in real time

### 📈 Spending Analytics
- Category-wise spending breakdown with progress bars
- Monthly breakdown list (last 6 months)
- Predictive month-end forecast with confidence level (low / medium / high)
- Spending trend analysis (month-over-month %)

### 🔔 Smart Alerts & Email Notifications (AWS SNS)
- In-app budget limit alerts (80% warning + 100% danger)
- **Real email alerts via AWS SNS** when categories exceed 80% or go over budget
- **Forecast overspend email** when projected month-end spend exceeds budget
- Emails sent to all subscribers of your configured SNS topic

### 🔍 Search & Filter Transactions
- **Keyword search** — live filter by title, notes, or category
- Filter by category (dropdown)
- Filter by month (date picker)
- All filters work simultaneously

### ☁️ Cloud Integration
- **AWS DynamoDB** — three tables: expenses, users, budgets
- **AWS SNS** — real email notifications
- **AWS EC2** — production deployment with Gunicorn + Nginx
- **AWS IAM** — least-privilege credential management
- **GitHub Actions CI/CD** — auto-deploy on push to `main`

---

## 📁 Project Structure

```
expense-tracker/
├── app.py                        ← Flask routes & entry point
├── config.py                     ← All configuration & env vars
├── requirements.txt              ← Python dependencies
├── setup_aws.py                  ← Creates all 3 DynamoDB tables
├── .env                          ← AWS credentials (NEVER commit!)
├── services/
│   ├── __init__.py
│   ├── db_service.py             ← DynamoDB CRUD + BudgetDynamoDBService
│   ├── expense_service.py        ← Business logic, forecasting, analytics
│   ├── notification_service.py  ← Budget alerts + AWS SNS email notifications
│   └── user_service.py          ← Registration, login, bcrypt hashing
├── static/
│   ├── style.css                 ← Dark-theme CSS
│   └── script.js                 ← Vanilla JS frontend (search, filters, charts)
├── templates/
│   ├── index.html                ← Main dashboard (single-page)
│   └── login.html                ← Login / signup page
├── systemd/
│   └── expense-tracker.service  ← systemd unit (EC2 production)
├── nginx/
│   └── expense-tracker.conf     ← Nginx reverse proxy config
└── .github/
    └── workflows/
        └── deploy.yml           ← CI/CD auto-deploy pipeline
```

---

## ⚡ Quick Start (Local)

### 1. Clone or navigate to the project
```bash
cd "expense-tracker"
```

### 2. Create & activate a virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Edit the `.env` file with your values:
```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-south-1

# DynamoDB Table Names
DYNAMODB_TABLE_NAME=ExpenseTracker
BUDGET_TABLE_NAME=ExpenseTrackerBudgets

# AWS SNS (optional — for email alerts)
# 1. Create an SNS Topic in the AWS Console (Standard type)
# 2. Subscribe your email to it and confirm
# 3. Paste the Topic ARN below
SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:123456789012:ExpenseTrackerAlerts

# Flask Settings
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_SECRET_KEY=your-secret-key
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### 5. Create the DynamoDB tables
```bash
python setup_aws.py
```
This creates **3 tables** automatically:
- `ExpenseTracker` — stores all expense records
- `ExpenseTrackerUsers` — stores user accounts (bcrypt hashed passwords)
- `ExpenseTrackerBudgets` — stores per-user monthly budgets (persistent)

### 6. Run the app
```bash
python app.py
```
Open your browser → **http://localhost:5000**

---

## 🌐 REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/login` | Login / signup page |
| POST | `/login` | Authenticate user |
| POST | `/signup` | Register new user |
| GET | `/logout` | End session |
| GET | `/api/expenses` | List all expenses (supports filters) |
| GET | `/api/expenses?category=Shopping` | Filter by category |
| GET | `/api/expenses?month=2026-05` | Filter by month |
| GET | `/api/expenses?search=coffee` | **Keyword search** (title/notes/category) |
| GET | `/api/expenses/<id>` | Get single expense |
| POST | `/api/expenses` | Create new expense |
| PUT | `/api/expenses/<id>` | Update expense |
| DELETE | `/api/expenses/<id>` | Delete expense |
| GET | `/api/summary` | Totals, category breakdown, alerts, trend |
| GET | `/api/forecast` | Month-end spending forecast |
| GET | `/api/budget` | Get user's monthly budget |
| POST | `/api/budget` | Set / update monthly budget |
| GET | `/api/health` | Health check (DynamoDB connectivity) |

### Example — Create Expense
```bash
curl -X POST http://localhost:5000/api/expenses \
  -H "Content-Type: application/json" \
  -d '{"title":"Coffee","amount":4.50,"category":"Food & Dining","date":"2026-05-08"}'
```

### Example — Keyword Search
```bash
curl "http://localhost:5000/api/expenses?search=zomato"
```

---

## 🗃️ DynamoDB Tables

### ExpenseTracker (Partition Key: `expense_id`)
| Field | Type | Description |
|-------|------|-------------|
| `expense_id` | String (PK) | Auto-generated UUID4 |
| `user_id` | String | Owner username |
| `title` | String | Expense description |
| `amount` | Number | Amount (₹) |
| `category` | String | Expense category |
| `date` | String | Date (YYYY-MM-DD) |
| `created_at` | String | ISO timestamp |
| `notes` | String | Optional notes |

### ExpenseTrackerUsers (Partition Key: `username`)
| Field | Type | Description |
|-------|------|-------------|
| `username` | String (PK) | Unique login name |
| `password_hash` | String | bcrypt hashed password |
| `created_at` | String | ISO timestamp |

### ExpenseTrackerBudgets (Partition Key: `username`)
| Field | Type | Description |
|-------|------|-------------|
| `username` | String (PK) | User's login name |
| `monthly_budget` | Number | Budget amount (₹) |
| `updated_at` | String | Last updated ISO timestamp |

**Billing Mode:** PAY_PER_REQUEST (On-Demand) on all tables.

---

## ☁️ AWS Deployment (Ubuntu EC2)

### Step 1 — Launch EC2 Instance
- AMI: **Ubuntu 22.04 LTS**
- Instance type: **t2.micro** (free tier)
- Storage: 8 GB

### Step 2 — Security Group Rules
| Type | Protocol | Port | Source |
|------|----------|------|--------|
| SSH | TCP | 22 | Your IP |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| Custom TCP | TCP | 5000 | 0.0.0.0/0 |

### Step 3 — IAM Permissions
Attach the following to your IAM user / EC2 role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable", "dynamodb:DescribeTable", "dynamodb:ListTables",
        "dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
        "dynamodb:DeleteItem", "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/ExpenseTracker*"
    },
    {
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:*:*:ExpenseTrackerAlerts"
    }
  ]
}
```

### Step 4 — SSH into EC2 and set up the server
```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx git

git clone https://github.com/yourname/expense-tracker.git
cd expense-tracker

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

nano .env   # Fill in your AWS credentials and SNS_TOPIC_ARN

python setup_aws.py   # Creates all 3 DynamoDB tables

sudo mkdir -p /var/log/expense-tracker
sudo chown ubuntu:ubuntu /var/log/expense-tracker
```

### Step 5 — Configure Gunicorn (systemd)
```bash
sudo cp systemd/expense-tracker.service /etc/systemd/system/
sudo nano /etc/systemd/system/expense-tracker.service   # Fix paths if needed
sudo systemctl daemon-reload
sudo systemctl enable expense-tracker
sudo systemctl start expense-tracker
sudo systemctl status expense-tracker
```

### Step 6 — Configure Nginx
```bash
sudo cp nginx/expense-tracker.conf /etc/nginx/sites-available/expense-tracker
sudo nano /etc/nginx/sites-available/expense-tracker   # Set server_name to EC2 IP
sudo ln -s /etc/nginx/sites-available/expense-tracker \
           /etc/nginx/sites-enabled/expense-tracker
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7 — Access the App
Open your browser → **http://\<EC2_PUBLIC_IP\>**

---

## 🔧 Useful Commands

```bash
# View live app logs
sudo journalctl -u expense-tracker -f

# Restart app after code changes
sudo systemctl restart expense-tracker

# Reload Nginx config
sudo systemctl reload nginx

# Health check
curl http://localhost:5000/api/health

# Re-run DynamoDB setup (safe — skips existing tables)
python setup_aws.py

# Deactivate virtual environment
deactivate
```

---

## 🏗️ Architecture

```
Browser (HTML + CSS + Vanilla JS)
    ↕  HTTP / Fetch API
Flask Routes (app.py)
    ↕  Function calls
├── expense_service.py   (business logic, analytics, forecast)
├── user_service.py      (auth, bcrypt, registration)
├── notification_service.py  (budget alerts + AWS SNS email)
└── db_service.py        (DynamoDB CRUD + BudgetDynamoDBService)
    ↕  boto3 AWS SDK
├── AWS DynamoDB         (ExpenseTracker, ExpenseTrackerUsers, ExpenseTrackerBudgets)
└── AWS SNS              (email notifications → subscribers)
```

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3 (custom dark theme), Vanilla JS |
| Backend | Python 3.11+, Flask 3.x |
| Database | AWS DynamoDB (NoSQL, On-Demand) |
| Notifications | AWS SNS (email alerts) |
| AWS SDK | boto3 |
| Auth | bcrypt (password hashing) |
| Production Server | Gunicorn |
| Reverse Proxy | Nginx |
| Process Manager | systemd |
| CI/CD | GitHub Actions |
| Hosting | AWS EC2 (Ubuntu 22.04) |
