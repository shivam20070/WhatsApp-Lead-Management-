# 🧠 Brain Checkers — Full Counseling Platform v3

## What's Included
- 🤖 **Chatbot** (`/`) — Public booking page with logo, QR payment, Meet/Address delivery
- 🔐 **Admin Login** (`/admin/login`) — Password protected
- 📊 **Admin Dashboard** (`/admin`) — Full management panel (company only)
- 🗄️ **SQLite Database** — All data persists forever (survives restarts)

## Run
```bash
pip install -r requirements.txt
python app.py
```
Open:
- Chatbot: http://127.0.0.1:5000
- Admin:   http://127.0.0.1:5000/admin/login

## Admin Credentials
```
Username: admin
Password: brain@2026
```
> Change these in app.py lines: ADMIN_USERNAME and ADMIN_PASSWORD

## Features

### Chatbot
- Validates name (letters only, min 2 chars)
- Validates phone (10-digit Indian mobile)
- Shows real UPI QR (shivamdhote5852@oki)
- Shows ONLY available slots (booked ones hidden)
- Online booking → Google Meet link sent to user
- Offline booking → Office address + Google Maps button

### Admin Dashboard
- **Overview** — Stats + today's meet sessions + recent bookings
- **All Bookings** — Full table with search, CSV export, confirm, delete
- **Meet Schedule** — All Google Meet links, Join button for counselors
- **Manage Slots** — Add/delete slots per day, see who booked which slot
- Auto-seed next day's slots button

### Slot System
- Each slot per date can only be booked ONCE
- Booked slots disappear from chatbot options
- Fresh slots available each new day automatically
- Admin can add custom slots or auto-seed defaults
- Deleting a booking frees the slot again

## File Structure
```
braincheckers/
├── app.py                    # Flask app + all routes
├── braincheckers.db          # SQLite DB (auto-created on first run)
├── requirements.txt
├── static/
│   ├── logo.png              # Brain Checkers logo
│   └── qr.jpeg               # UPI payment QR
└── templates/
    ├── chatbot.html          # Public chatbot page
    ├── login.html            # Admin login
    └── admin.html            # Admin dashboard
```
