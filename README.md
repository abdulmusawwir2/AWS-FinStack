# Expense Tracker — Full-Stack Flask + AWS DynamoDB

> A clean, modern, single-page expense tracking dashboard built with
> **Python Flask**, **Vanilla JavaScript**, and **AWS DynamoDB**.

---

## 📁 Project Structure

```
expense-tracker/
├── app.py                        ← Flask routes & entry point
├── config.py                     ← All configuration & env vars
├── requirements.txt              ← Python dependencies
├── setup_aws.py                  ← Creates DynamoDB table
├── .env                          ← AWS credentials (NEVER commit!)
├── services/
│   ├── __init__.py
│   ├── db_service.py             ← DynamoDB CRUD (boto3)
│   ├── expense_service.py        ← Business logic & validation
│   └── notification_service.py  ← Budget alerts & trends
├── static/
│   ├── style.css                 ← Dark-theme CSS
│   └── script.js                 ← Vanilla JS frontend
├── templates/
│   └── index.html                ← Single-page dashboard
├── systemd/
│   └── expense-tracker.service  ← systemd unit (EC2)
└── nginx/
    └── expense-tracker.conf     ← Nginx reverse proxy (EC2)
```

---

## ⚡ Quick Start (Local)

### 1. Clone or navigate to the project
```bash
cd expense-tracker
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

### 4. Configure AWS credentials
Edit the `.env` file:
```env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=ExpenseTracker
FLASK_DEBUG=True
FLASK_SECRET_KEY=my-super-secret-key
```

### 5. Create the DynamoDB table
```bash
python setup_aws.py
```

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
| GET | `/api/expenses` | List all expenses |
| GET | `/api/expenses?category=Shopping` | Filter by category |
| GET | `/api/expenses?month=2026-05` | Filter by month |
| GET | `/api/expenses/<id>` | Get single expense |
| POST | `/api/expenses` | Create new expense |
| PUT | `/api/expenses/<id>` | Update expense |
| DELETE | `/api/expenses/<id>` | Delete expense |
| GET | `/api/summary` | Get totals & statistics |
| GET | `/api/health` | Health check |

### Example — Create Expense
```bash
curl -X POST http://localhost:5000/api/expenses \
  -H "Content-Type: application/json" \
  -d '{"title":"Coffee","amount":4.50,"category":"Food & Dining","date":"2026-05-08"}'
```

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

### Step 3 — IAM Permissions for your EC2 / IAM user
Attach this inline policy or use `AmazonDynamoDBFullAccess` (for learning):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "dynamodb:CreateTable", "dynamodb:DescribeTable",
      "dynamodb:PutItem", "dynamodb:GetItem",
      "dynamodb:UpdateItem", "dynamodb:DeleteItem",
      "dynamodb:Scan", "dynamodb:ListTables"
    ],
    "Resource": "arn:aws:dynamodb:*:*:table/ExpenseTracker"
  }]
}
```

### Step 4 — SSH into EC2 and set up the server
```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, pip, Nginx
sudo apt install -y python3-pip python3-venv nginx git

# Clone or upload project
git clone https://github.com/yourname/expense-tracker.git
cd expense-tracker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env .env.backup
nano .env   # Fill in your AWS credentials

# Create DynamoDB table
python setup_aws.py

# Create log directory
sudo mkdir -p /var/log/expense-tracker
sudo chown ubuntu:ubuntu /var/log/expense-tracker
```

### Step 5 — Configure Gunicorn (systemd)
```bash
# Copy service file
sudo cp systemd/expense-tracker.service /etc/systemd/system/

# Edit paths if needed
sudo nano /etc/systemd/system/expense-tracker.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable expense-tracker
sudo systemctl start expense-tracker
sudo systemctl status expense-tracker
```

### Step 6 — Configure Nginx
```bash
# Copy Nginx config
sudo cp nginx/expense-tracker.conf /etc/nginx/sites-available/expense-tracker

# Edit server_name to your EC2 IP
sudo nano /etc/nginx/sites-available/expense-tracker

# Enable site
sudo ln -s /etc/nginx/sites-available/expense-tracker \
           /etc/nginx/sites-enabled/expense-tracker

# Remove default (optional)
sudo rm -f /etc/nginx/sites-enabled/default

# Test & reload
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7 — Access the App
Open your browser → **http://\<EC2_PUBLIC_IP\>**

---

## 🗃️ DynamoDB Table Schema

| Field | Type | Description |
|-------|------|-------------|
| `expense_id` | String (PK) | Auto-generated UUID4 |
| `title` | String | Expense title |
| `amount` | Number | Amount in USD |
| `category` | String | Expense category |
| `date` | String | Date (YYYY-MM-DD) |
| `created_at` | String | ISO timestamp |
| `notes` | String | Optional notes |

**Billing Mode:** PAY_PER_REQUEST (On-Demand) — no capacity planning needed.

---

## 🔧 Useful Commands

```bash
# View app logs
sudo journalctl -u expense-tracker -f

# Restart app
sudo systemctl restart expense-tracker

# Reload Nginx
sudo systemctl reload nginx

# Health check
curl http://localhost:5000/api/health

# Deactivate virtualenv
deactivate
```

---

## 🏗️ Architecture

```
Browser (HTML + CSS + JS)
    ↕  HTTP / Fetch API
Flask Routes (app.py)
    ↕  Function calls
Expense Service (business logic)
    ↕  Function calls
DB Service (boto3)
    ↕  AWS API
DynamoDB (AWS)
```

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3 (custom), Vanilla JS |
| Backend | Python 3.11+, Flask 3.0 |
| Database | AWS DynamoDB (NoSQL) |
| AWS SDK | boto3 |
| Production Server | Gunicorn |
| Reverse Proxy | Nginx |
| Process Manager | systemd |
| Hosting | AWS EC2 (Ubuntu 22.04) |
