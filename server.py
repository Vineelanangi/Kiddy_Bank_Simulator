from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
import os
import qrcode
import random
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import smtplib
#Load .env vriables
load_dotenv(dotenv_path='kiddy_bank_project\.env')
#Secure secrets
EMAIL_ADDRESS= os.getenv('EMAIL_USER')
EMAIL_PASSWORD= os.getenv('EMAIL_PASSWORD')
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# MySQL Configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')

mysql = MySQL(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Auto-create upload folder if missing
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

confirm_codes = {}

@app.route('/')
def main():
    return render_template('main.html')
def send_otp(recipient_email):
    try:
        otp = str(random.randint(1000, 9999))
        sender_email = EMAIL_ADDRESS
        sender_password = EMAIL_PASSWORD

        subject = "Kiddy Bank OTP Verification"
        body = f"Your OTP for registration is: {otp}"

        message = f"Subject: {subject}\n\n{body}"

        # Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS,EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, recipient_email, message)
        server.quit()

        return otp
    except Exception as e:
        print("Email sending failed:", str(e))
        return None


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form['email'].strip()

        cursor = mysql.connection.cursor()

        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cursor.fetchone()

        if 'send_otp' in request.form:
            if existing_user:
                flash("⚠️ User already exists. Please click login.")
                return render_template('register.html')

            otp = send_otp(email)
            if otp:
                session['otp'] = otp
                session['temp_username'] = username
                session['temp_password'] = password
                session['temp_email'] = email
                session['otp_sent'] = True
                flash("📩 OTP sent to your email.")
            else:
                flash("❌ Failed to send OTP. Please try again.")
            cursor.close()
            return render_template('register.html')

        elif 'register' in request.form:
            otp_input = request.form['otp_input'].strip()
            if otp_input != session.get('otp'):
                flash("❌ Invalid OTP. Please send OTP again.")
                session.pop('otp', None)
                session.pop('otp_sent', None)
                session.pop('temp_username', None)
                session.pop('temp_password', None)
                session.pop('temp_email', None)
                cursor.close()
                return render_template('register.html')

            if existing_user:
                flash("⚠️ User already exists. Please click login.")
                session.pop('otp', None)
                session.pop('otp_sent', None)
                session.pop('temp_username', None)
                session.pop('temp_password', None)
                session.pop('temp_email', None)
                cursor.close()
                return render_template('register.html')

            # Insert into DB
            cursor.execute("INSERT INTO users (username, password, balance, email, goal) VALUES (%s, %s, %s, %s, %s)",
                           (session['temp_username'], session['temp_password'], 0, session['temp_email'], 500))
            mysql.connection.commit()
            cursor.close()

            # Clear session
            session.pop('otp', None)
            session.pop('otp_sent', None)
            session.pop('temp_username', None)
            session.pop('temp_password', None)
            session.pop('temp_email', None)

            session['new_user'] = username
            flash("✅ Registration successful. Please click login.")
            return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    username_prefill = session.pop('new_user', '')  # Autofill after registration

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session['username'] = username
            return redirect('/dashboard')
        else:
            flash("❌ Invalid username or password")
            return render_template('login.html', prefill_username=username)

    return render_template('login.html', prefill_username=username_prefill)
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username'].strip()
        new_password = request.form['new_password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            flash("❌ Username not found.")
            cursor.close()
            return redirect('/forgot_password')

        cursor.execute("UPDATE users SET password = %s WHERE username = %s", (new_password, username))
        mysql.connection.commit()
        cursor.close()

        flash("✅ Password reset successful. You can now log in.")
        return redirect('/login')

    return render_template('forgot_password.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT balance, goal FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    if not result:
        flash("User not found.")
        return redirect('/login')
    balance, goal = result

    cursor.execute("SELECT description, created_at FROM transactions WHERE username = %s ORDER BY created_at DESC", (username,))
    transactions = cursor.fetchall()
    cursor.close()

    transaction_list = [f"{desc} at {time.strftime('%H:%M:%S')}" for desc, time in transactions]

    # Generate new confirm code and QR
# Generate new confirm code and QR
    code = str(random.randint(1000, 9999))
    session['confirm_code'] = code  # Store in session instead of confirm_codes dict
    session['code_used']=False
    img = qrcode.make(f'Confirm code: {code}')
    qr_path = f'static/qr_{username}.png'
    img.save(qr_path)
    return render_template('dashboard.html',
                           username=username,
                           balance=balance,
                           goal=goal,
                           transactions=transaction_list,
                           qr_code_path=qr_path,
                           success=request.args.get('success'),
                           goal_updated=request.args.get('goal_updated'),now=datetime.now())

@app.route('/confirm_deposit', methods=['POST'])
def confirm_deposit():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    entered_code = request.form.get('confirm_code', '').strip()
    correct_code = session.get('confirm_code')

    print(f"DEBUG: Entered code = {entered_code}, Correct code = {correct_code}")

    if entered_code == correct_code:
        # ✅ Only allow deposit if form is submitted manually (scan does not auto-submit)
        # For safety, allow deposit only once per valid code
        if session.get('code_used'):
            flash("⚠️ This code was already used.")
            return redirect('/dashboard')

        amount = random.randint(10, 100)

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, username))
        cursor.execute("INSERT INTO transactions (username, description) VALUES (%s, %s)",
                       (username, f"Deposited ₹{amount} via Confirm Code"))
        mysql.connection.commit()
        cursor.close()

        print(f"DEBUG: Manually submitted code - Added ₹{amount} for {username}")

        # ✅ Mark this code as used
        session['code_used'] = True
        session.pop('confirm_code', None)

        flash(f"✅ ₹{amount} deposited via confirm code.")
        return redirect('/dashboard?success=1')
    else:
        flash("❌ Invalid confirmation code.")
        return redirect('/dashboard')
@app.route('/upload_qr', methods=['POST'])
def upload_qr():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    file = request.files.get('qr_image')

    if not file or file.filename == '':
        flash("No QR file selected.")
        return redirect('/dashboard')

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        amount = random.randint(10, 100)
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, username))
        cursor.execute("INSERT INTO transactions (username, description) VALUES (%s, %s)",
                       (username, f"Deposited ₹{amount} via QR image"))
        
        mysql.connection.commit()
        cursor.close()

        flash(f"✅ ₹{amount} deposited via QR upload.")
        return redirect('/dashboard')
    else:
        flash("Invalid file type. Upload PNG/JPG only.")
        return redirect('/dashboard')

@app.route('/update_goal', methods=['POST'])
def update_goal():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    try:
        new_goal = int(request.form['new_goal'])
        if new_goal <= 0:
            raise ValueError
    except:
        flash("Please enter a valid positive number for your goal.")
        return redirect('/dashboard')

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET goal = %s WHERE username = %s", (new_goal, username))
    mysql.connection.commit()
    cursor.close()

    flash("🎯 Savings goal updated.")
    return redirect('/dashboard?goal_updated=1')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    flash("Logged out.")
    return redirect('/login')

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)