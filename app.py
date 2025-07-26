from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
import re
import random
import string

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# ========== DATABASE CONNECTION ==========
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ========== INITIAL DATABASE SETUP ==========
def init_db():
    conn = get_db()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    # Insert admin if not exists
    admin = conn.execute("SELECT * FROM users WHERE username = ?", ("Shishir",)).fetchone()
    if not admin:
        conn.execute("INSERT INTO users (username, password, is_admin, balance, email_verified, phone_verified) VALUES (?, ?, ?, ?, ?, ?)", ("Shishir", "378625", 1, 0, 1, 1))
        conn.commit()

if not os.path.exists('database.db'):
    init_db()

# ========== UTILITIES ==========

def is_logged_in():
    return 'user_id' in session

def is_admin():
    return 'admin_id' in session

def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# ========== ROUTES ==========

@app.route('/')
def index():
    return render_template('index.html')

# -------- USER AUTH --------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        # Basic validations
        if not username or not password:
            flash("Username and password required.")
            return render_template('register.html')

        # Email and phone optional, but if provided, validate format
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email format.")
            return render_template('register.html')

        if phone and not re.match(r"^\+?\d{10,15}$", phone):
            flash("Invalid phone number.")
            return render_template('register.html')

        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Username already taken.")
            return render_template('register.html')

        # Save user but mark email_verified, phone_verified = 0 initially
        conn.execute(
            "INSERT INTO users (username, password, email, phone, is_admin, balance, email_verified, phone_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, password, email, phone, 0, 0, 0, 0)
        )
        conn.commit()

        # TODO: Send email/phone verification code here (out of scope)

        flash("Registered successfully! Please login.")
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        if user:
            if user['is_banned']:
                flash("Your account is banned.")
                return render_template('login.html')
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            if user['is_admin']:
                session['admin_id'] = user['id']
                return redirect('/admin/dashboard')
            else:
                return redirect('/dashboard')
        flash("Invalid username or password.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# -------- USER DASHBOARD --------

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect('/login')
    user_id = session['user_id']
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    tournaments = conn.execute("SELECT * FROM tournaments ORDER BY time DESC").fetchall()
    balance = user['balance']
    return render_template('dashboard.html', user=user, tournaments=tournaments, balance=balance)

# -------- TOURNAMENT JOIN --------

@app.route('/join/<int:tournament_id>', methods=['GET', 'POST'])
def join(tournament_id):
    if not is_logged_in():
        return redirect('/login')
    if request.method == 'POST':
        team_name = request.form['team_name'].strip()
        uid = request.form['uid'].strip()
        user_id = session['user_id']

        conn = get_db()
        # Check if already joined
        existing = conn.execute("SELECT * FROM participants WHERE user_id=? AND tournament_id=?", (user_id, tournament_id)).fetchone()
        if existing:
            flash("You already joined this tournament.")
            return redirect('/dashboard')

        # Insert participant
        conn.execute(
            "INSERT INTO participants (user_id, tournament_id, team_name, uid, approved) VALUES (?, ?, ?, ?, ?)",
            (user_id, tournament_id, team_name, uid, 0)
        )
        conn.commit()
        flash("Joined tournament successfully! Waiting for admin approval.")
        return redirect('/dashboard')

    return render_template('join.html', tournament_id=tournament_id)

# -------- REDEEM SYSTEM --------

@app.route('/redeem', methods=['GET', 'POST'])
def redeem():
    if not is_logged_in():
        return redirect('/login')
    user_id = session['user_id']
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    if request.method == 'POST':
        amount = int(request.form['amount'])
        method = request.form['method']
        number = request.form['number'].strip()

        if amount <= 0:
            flash("Invalid amount.")
            return redirect('/redeem')

        if user['balance'] < amount:
            flash("Insufficient balance.")
            return redirect('/redeem')

        conn.execute(
            "INSERT INTO redeem_requests (user_id, amount, method, number, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, method, number, 'pending')
        )
        # Deduct immediately (optional: or deduct after approval)
        conn.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, user_id))
        conn.commit()
        flash("Redeem request submitted!")
        return redirect('/dashboard')

    return render_template('redeem.html', balance=user['balance'])

# -------- ADMIN AUTH --------

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        admin = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND is_admin=1", (username, password)).fetchone()
        if admin:
            session['admin_id'] = admin['id']
            session['username'] = admin['username']
            return redirect('/admin/dashboard')
        flash("Invalid admin credentials.")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('username', None)
    return redirect('/admin')

# -------- ADMIN DASHBOARD --------

@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    tournaments = conn.execute("SELECT * FROM tournaments ORDER BY time DESC").fetchall()
    participants = conn.execute("SELECT * FROM participants").fetchall()
    redeem_requests = conn.execute("SELECT * FROM redeem_requests ORDER BY id DESC").fetchall()
    notifications = conn.execute("SELECT * FROM notifications ORDER BY id DESC").fetchall()
    return render_template('admin_dashboard.html', users=users, tournaments=tournaments, participants=participants, redeems=redeem_requests, notifications=notifications)

# -------- TOURNAMENT CREATE / EDIT / DELETE --------

@app.route('/admin/create_tournament', methods=['GET', 'POST'])
def create_tournament():
    if not is_admin():
        return redirect('/admin')
    if request.method == 'POST':
        title = request.form['title'].strip()
        time = request.form['time'].strip()
        entry_fee = int(request.form['entry_fee'])
        prize_pool = request.form['prize_pool'].strip()
        conn = get_db()
        conn.execute("INSERT INTO tournaments (title, time, entry_fee, prize_pool) VALUES (?, ?, ?, ?)",
                     (title, time, entry_fee, prize_pool))
        conn.commit()
        flash("Tournament created!")
        return redirect('/admin/dashboard')
    return render_template('create_tournament.html')

@app.route('/admin/edit_tournament/<int:tournament_id>', methods=['GET', 'POST'])
def edit_tournament(tournament_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    tournament = conn.execute("SELECT * FROM tournaments WHERE id=?", (tournament_id,)).fetchone()
    if not tournament:
        flash("Tournament not found.")
        return redirect('/admin/dashboard')
    if request.method == 'POST':
        title = request.form['title'].strip()
        time = request.form['time'].strip()
        entry_fee = int(request.form['entry_fee'])
        prize_pool = request.form['prize_pool'].strip()
        status = request.form['status']
        conn.execute("UPDATE tournaments SET title=?, time=?, entry_fee=?, prize_pool=?, status=? WHERE id=?",
                     (title, time, entry_fee, prize_pool, status, tournament_id))
        conn.commit()
        flash("Tournament updated!")
        return redirect('/admin/dashboard')
    return render_template('edit_tournament.html', tournament=tournament)

@app.route('/admin/delete_tournament/<int:tournament_id>')
def delete_tournament(tournament_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    conn.execute("DELETE FROM tournaments WHERE id=?", (tournament_id,))
    conn.execute("DELETE FROM participants WHERE tournament_id=?", (tournament_id,))
    conn.commit()
    flash("Tournament deleted!")
    return redirect('/admin/dashboard')

# -------- PARTICIPANT APPROVE / REJECT --------

@app.route('/admin/approve_participant/<int:participant_id>')
def approve_participant(participant_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    conn.execute("UPDATE participants SET approved=1 WHERE id=?", (participant_id,))
    conn.commit()
    flash("Participant approved.")
    return redirect('/admin/dashboard')

@app.route('/admin/reject_participant/<int:participant_id>')
def reject_participant(participant_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    conn.execute("DELETE FROM participants WHERE id=?", (participant_id,))
    conn.commit()
    flash("Participant rejected and removed.")
    return redirect('/admin/dashboard')

# -------- REDEEM REQUEST APPROVE / REJECT --------

@app.route('/admin/approve_redeem/<int:redeem_id>')
def approve_redeem(redeem_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    conn.execute("UPDATE redeem_requests SET status='approved' WHERE id=?", (redeem_id,))
    conn.commit()
    flash("Redeem request approved.")
    return redirect('/admin/dashboard')

@app.route('/admin/reject_redeem/<int:redeem_id>')
def reject_redeem(redeem_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    redeem = conn.execute("SELECT * FROM redeem_requests WHERE id=?", (redeem_id,)).fetchone()
    if redeem and redeem['status'] == 'pending':
        # Refund amount to user
        conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (redeem['amount'], redeem['user_id']))
    conn.execute("UPDATE redeem_requests SET status='rejected' WHERE id=?", (redeem_id,))
    conn.commit()
    flash("Redeem request rejected and amount refunded.")
    return redirect('/admin/dashboard')

# -------- ADD BALANCE TO USER --------

@app.route('/admin/add_balance/<int:user_id>', methods=['GET', 'POST'])
def add_balance(user_id):
    if not is_admin():
        return redirect('/admin')
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        flash("User not found.")
        return redirect('/admin/dashboard')

    if request.method == 'POST':
        amount = int(request.form['amount'])
        if amount <= 0:
            flash("Invalid amount.")
            return redirect(f'/admin/add_balance/{user_id}')
        conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
        conn.commit()
        flash("Balance added.")
        return redirect('/admin/dashboard')
    return render_template('add_balance.html', user=user)

# -------- NOTIFICATION SYSTEM --------

@app.route('/admin/create_notification', methods=['GET', 'POST'])
def create_notification():
    if not is_admin():
        return redirect('/admin')
    if request.method == 'POST':
        message = request.form['message'].strip()
        conn = get_db()
        conn.execute("INSERT INTO notifications (message) VALUES (?)", (message,))
        conn.commit()
        flash("Notification sent.")
        return redirect('/admin/dashboard')
    return render_template('create_notification.html')

@app.route('/notifications')
def notifications():
    conn = get_db()
    notes = conn.execute("SELECT * FROM notifications ORDER BY id DESC").fetchall()
    return render_template('notifications.html', notifications=notes)

# -------- EMAIL / PHONE VERIFICATION PLACEHOLDER --------

# (You can extend this with actual email/SMS sending services)

# -------- RUN --------

if __name__ == '__main__':
    app.run(debug=True)
