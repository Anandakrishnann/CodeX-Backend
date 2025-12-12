🧠 CodexLearning Backend

The **CodexLearning Backend** is a scalable, production-ready API built using **Django + Django REST Framework (DRF)**.  
It powers the entire e-learning platform — managing authentication, tutor applications, courses, payments, and video meetings.

---

## 🌟 Key Features

### 🔐 Authentication
- Custom user model with roles: **User**, **Tutor**, **Admin**.
- **JWT authentication** for secure login sessions.
- **Google OAuth** support.
- OTP-based registration for extra verification.

### 🎓 Tutor Management
- Multi-step tutor verification form with:
  - Profile picture upload  
  - Document verification  
  - Video proof submission
- Admin verification workflow before approval.

### 📚 Course Management
- Tutors can create and manage courses.
- Each course includes modules and lessons.
- Track enrolled students and progress data.

### 💬 Real-Time Collaboration
- Integrated **ZegoCloud** video call and chat system.
- Tutors can schedule meetings.
- Users can book and join meetings instantly.
- Automatic **email reminders** before sessions (via **Celery**).

### 💳 Payment & Subscription
- **Stripe integration** for subscriptions and payments.
- Handles checkout sessions and webhook updates.
- Automatically updates user/tutor subscription data.

### 🧑‍💼 Admin Dashboard
- Manage all users, tutors, and courses.
- Approve or reject tutor applications.
- Monitor payments, subscriptions, and analytics.

---

## 🛠 Tech Stack

- **Python 3.11+**
- **Django 5+**
- **Django REST Framework (DRF)**
- **PostgreSQL**
- **Celery + Redis**
- **Stripe API**
- **ZegoCloud SDK**
- **JWT Authentication**

---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repository
```bash
git clone https://github.com/your-username/codexlearning-backend.git
cd codexlearning-backend

2️⃣ Create Virtual Environment
python -m venv venv
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate        # Windows

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Configure Environment Variables
Create a .env file in your Backend/CodeX folder:

# ===============================
# DJANGO SETTINGS
# ===============================
SECRET_KEY=your_secret_key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# ===============================
# DATABASE SETTINGS
# ===============================
DB_NAME=codexlearning
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# ===============================
# EMAIL SETTINGS
# ===============================
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
DEFAULT_FROM_EMAIL=your_email@example.com

# ===============================
# STRIPE SETTINGS
# ===============================
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLIC_KEY=your_stripe_public_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# ===============================
# ZEGO CLOUD SETTINGS
# ===============================
ZEGO_APP_ID=your_zegocloud_app_id
ZEGO_SERVER_SECRET=your_zegocloud_secret

# ===============================
# REDIS & CELERY
# ===============================
REDIS_URL=redis://localhost:6379

5️⃣ Run Database Migrations
python manage.py makemigrations
python manage.py migrate

6️⃣ Create Admin User
python manage.py createsuperuser

7️⃣ Start Server
python manage.py runserver
Your API will be live on 👉 http://127.0.0.1:8000/

🧱 Folder Structure
Backend/
└── CodeX/
    ├── Accounts/
    ├── adminpanel/
    ├── chat/
    ├── tutorpanel/
    ├── notifications/
    ├── templates/
    ├── CodeX/
    ├── manage.py
    ├── requirements.txt
    └── .env
🧩 API Overview
Endpoint	Method	Description
/api/signup/	POST	Register user
/api/login/	POST	Authenticate user
/api/applications/	POST	Tutor application
/api/courses/	GET	List all courses
/api/meetings/	GET/POST	Manage meetings
/api/stripe/checkout/	POST	Create payment session
/api/stripe/webhook/	POST	Stripe webhook handler

🧑‍💻 Author
👨‍💻 Anandha Krishnan P S
B.Sc Electronics graduate → Self-taught Full-Stack Developer.
Passionate about problem-solving, scalable backends, and real-time collaboration tools.

📫 Email: kanandha808@gmail.com
🔗 LinkedIn: linkedin.com/in/anandhakrishnnn

⭐ Support
If this project inspires or helps you, give it a ⭐ on GitHub — it motivates continued development!
