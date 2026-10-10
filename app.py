from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, session, abort
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime
import sqlite3
import uuid
import os

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'civilathon.db'
UPLOAD_DIR = BASE_DIR / 'uploads' / 'ppt'
PAYMENT_PROOF_DIR = BASE_DIR / 'uploads' / 'payment_proofs'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PAYMENT_PROOF_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.ppt', '.pptx'}
ALLOWED_PROOF_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.pdf'}
MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_PROOF_SIZE = 8 * 1024 * 1024
TEAM_FEE = 14900       # ₹149 in paise
INDIVIDUAL_FEE = 4900  # ₹49 in paise

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'local-development-only-change-this-secret')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE + MAX_PROOF_SIZE

DOMAINS = [
    'Smart Construction & Construction Management',
    'Sustainable & Green Construction',
    'Innovative Construction Materials',
    'AI/ML & Automation',
    'IoT & Smart Infrastructure',
    'GIS, Surveying & Geospatial Technology',
    'Transportation & Smart Mobility',
    'Water Resources & Management',
    'Smart Cities & Urban Infrastructure',
    'Structural Engineering & Safety',
    'Waste Management & Circular Construction',
    'Any Other Real-World Civil Engineering Problem',
]

UPI_ID = os.getenv('CIVILATHON_UPI_ID', '9713559328@axl').strip()
ADMIN_PASSWORD = os.getenv('CIVILATHON_ADMIN_PASSWORD', '').strip()
PAYMENT_QR_PATH = BASE_DIR / 'static' / 'images' / 'payment-qr.png'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id TEXT UNIQUE NOT NULL,
            participation_type TEXT NOT NULL,
            team_name TEXT,
            college TEXT NOT NULL,
            leader_name TEXT NOT NULL,
            leader_mobile TEXT NOT NULL,
            leader_email TEXT NOT NULL,
            member_2 TEXT,
            member_3 TEXT,
            member_4 TEXT,
            research_domain TEXT NOT NULL,
            problem_statement TEXT NOT NULL,
            proposed_solution TEXT NOT NULL,
            innovation TEXT NOT NULL,
            expected_impact TEXT NOT NULL,
            ppt_filename TEXT NOT NULL,
            ppt_path TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'Pending',
            payment_id TEXT,
            payment_order_id TEXT,
            payment_signature TEXT,
            amount_paise INTEGER,
            created_at TEXT NOT NULL,
            paid_at TEXT,
            payment_reference TEXT,
            payment_screenshot_path TEXT,
            payment_submitted_at TEXT,
            admin_note TEXT
        )
    ''')
    # Safe migration for databases created by earlier Stage 3 builds.
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(registrations)').fetchall()}
    migrations = {
        'payment_order_id': 'ALTER TABLE registrations ADD COLUMN payment_order_id TEXT',
        'payment_signature': 'ALTER TABLE registrations ADD COLUMN payment_signature TEXT',
        'amount_paise': 'ALTER TABLE registrations ADD COLUMN amount_paise INTEGER',
        'paid_at': 'ALTER TABLE registrations ADD COLUMN paid_at TEXT',
        'payment_reference': 'ALTER TABLE registrations ADD COLUMN payment_reference TEXT',
        'payment_screenshot_path': 'ALTER TABLE registrations ADD COLUMN payment_screenshot_path TEXT',
        'payment_submitted_at': 'ALTER TABLE registrations ADD COLUMN payment_submitted_at TEXT',
        'admin_note': 'ALTER TABLE registrations ADD COLUMN admin_note TEXT',
    }
    for name, sql in migrations.items():
        if name not in columns:
            conn.execute(sql)
    conn.commit()
    conn.close()


def allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def make_registration_id():
    return f"CIV-26-{uuid.uuid4().hex[:6].upper()}"


def allowed_proof(filename):
    return Path(filename).suffix.lower() in ALLOWED_PROOF_EXTENSIONS


@app.context_processor
def inject_common():
    return {'event_domains': DOMAINS, 'upi_id': UPI_ID}


@app.route('/')
def home():
    return render_template('index.html')


@app.get('/about')
def about():
    return render_template('about.html')

@app.get('/domains')
def domains():
    return render_template('domains.html')

@app.get('/rules')
def rules():
    return render_template('rules.html')

@app.get('/guidelines')
def guidelines():
    return render_template('guidelines.html')

@app.get('/submission')
def submission():
    return render_template('submission.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html', domains=DOMAINS)

    participation_type = request.form.get('participation_type', '').strip().lower()
    team_name = request.form.get('team_name', '').strip()
    college = request.form.get('college', '').strip()
    leader_name = request.form.get('leader_name', '').strip()
    leader_mobile = request.form.get('leader_mobile', '').strip()
    leader_email = request.form.get('leader_email', '').strip()
    member_2 = request.form.get('member_2', '').strip()
    member_3 = request.form.get('member_3', '').strip()
    member_4 = request.form.get('member_4', '').strip()
    research_domain = request.form.get('research_domain', '').strip()
    problem_statement = request.form.get('problem_statement', '').strip()
    proposed_solution = request.form.get('proposed_solution', '').strip()
    innovation = request.form.get('innovation', '').strip()
    expected_impact = request.form.get('expected_impact', '').strip()
    ppt = request.files.get('ppt')

    errors = []
    if participation_type not in {'team', 'individual'}:
        errors.append('Please select team or individual participation.')
    if not college:
        errors.append('College name is required.')
    if not leader_name:
        errors.append('Participant/team leader name is required.')
    if not leader_mobile or not leader_mobile.replace('+', '').replace(' ', '').isdigit():
        errors.append('Enter a valid mobile number.')
    if not leader_email or '@' not in leader_email:
        errors.append('Enter a valid email address.')
    if not research_domain or research_domain not in DOMAINS:
        errors.append('Please select a valid research domain.')
    for label, value in [
        ('problem statement', problem_statement),
        ('proposed solution', proposed_solution),
        ('innovation', innovation),
        ('expected impact', expected_impact),
    ]:
        if not value:
            errors.append(f'{label.capitalize()} is required.')

    if participation_type == 'team':
        if not team_name:
            errors.append('Team name is required for team participation.')
        members = [member_2, member_3, member_4]
        if not any(members):
            errors.append('Add at least one additional team member for team participation.')
    else:
        team_name = ''
        member_2 = member_3 = member_4 = ''

    if not ppt or not ppt.filename:
        errors.append('Please upload your final PPT/PPTX.')
    elif not allowed_file(ppt.filename):
        errors.append('Only .ppt and .pptx files are accepted.')

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('register.html', domains=DOMAINS), 400

    registration_id = make_registration_id()
    original_name = secure_filename(ppt.filename)
    stored_name = f'{registration_id}_{original_name}'
    stored_path = UPLOAD_DIR / stored_name
    ppt.save(stored_path)

    amount_paise = TEAM_FEE if participation_type == 'team' else INDIVIDUAL_FEE
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute('''
        INSERT INTO registrations (
            registration_id, participation_type, team_name, college,
            leader_name, leader_mobile, leader_email, member_2, member_3,
            member_4, research_domain, problem_statement, proposed_solution,
            innovation, expected_impact, ppt_filename, ppt_path,
            payment_status, amount_paise, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        registration_id, participation_type, team_name, college,
        leader_name, leader_mobile, leader_email, member_2, member_3,
        member_4, research_domain, problem_statement, proposed_solution,
        innovation, expected_impact, original_name, str(stored_path),
        'Pending', amount_paise, created_at
    ))
    conn.commit()
    conn.close()

    return redirect(url_for('payment', registration_id=registration_id))


@app.route('/payment/<registration_id>', methods=['GET', 'POST'])
def payment(registration_id):
    conn = get_db()
    registration = conn.execute('SELECT * FROM registrations WHERE registration_id = ?', (registration_id,)).fetchone()
    conn.close()
    if not registration:
        return render_template('page.html', title='Registration Not Found', content='<p class="lead-dark">The registration ID could not be found.</p>'), 404
    if registration['payment_status'] == 'Paid':
        return redirect(url_for('success', registration_id=registration_id))

    if request.method == 'POST':
        reference = request.form.get('payment_reference', '').strip()
        proof = request.files.get('payment_screenshot')
        errors = []
        if not reference or len(reference) < 6:
            errors.append('Enter the UPI transaction/reference ID shown in your payment app.')
        if not proof or not proof.filename:
            errors.append('Upload a screenshot or PDF of your payment confirmation.')
        elif not allowed_proof(proof.filename):
            errors.append('Payment proof must be PNG, JPG, WEBP, or PDF.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('payment', registration_id=registration_id))

        proof_name = secure_filename(proof.filename)
        stored_name = f"{registration_id}_{uuid.uuid4().hex[:8]}_{proof_name}"
        stored_path = PAYMENT_PROOF_DIR / stored_name
        proof.save(stored_path)
        submitted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        conn.execute("UPDATE registrations SET payment_reference = ?, payment_screenshot_path = ?, payment_submitted_at = ?, payment_status = 'Pending Verification', admin_note = NULL WHERE registration_id = ? AND payment_status != 'Paid'",
                     (reference, str(stored_path), submitted_at, registration_id))
        conn.commit()
        conn.close()
        flash('Payment proof submitted. Your registration is pending manual verification.', 'success')
        return redirect(url_for('success', registration_id=registration_id))

    return render_template('payment.html', registration=registration, amount=registration['amount_paise'] / 100,
                           qr_available=PAYMENT_QR_PATH.exists())


def admin_required():
    if not session.get('civilathon_admin'):
        return redirect(url_for('admin_login'))
    return None


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not ADMIN_PASSWORD:
            flash('Admin password is not configured. Set CIVILATHON_ADMIN_PASSWORD in the hosting environment.', 'error')
        elif hmac_compare(password, ADMIN_PASSWORD):
            session['civilathon_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password.', 'error')
    return render_template('admin_login.html')


def hmac_compare(a, b):
    import hmac
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('civilathon_admin', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_dashboard():
    gate = admin_required()
    if gate:
        return gate
    conn = get_db()
    rows = conn.execute('SELECT * FROM registrations ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin.html', registrations=rows)


@app.route('/admin/payment-proof/<registration_id>')
def admin_payment_proof(registration_id):
    gate = admin_required()
    if gate:
        return gate
    conn = get_db()
    row = conn.execute('SELECT payment_screenshot_path FROM registrations WHERE registration_id = ?', (registration_id,)).fetchone()
    conn.close()
    if not row or not row['payment_screenshot_path']:
        abort(404)
    path = Path(row['payment_screenshot_path']).resolve()
    if path.parent != PAYMENT_PROOF_DIR.resolve() or not path.is_file():
        abort(404)
    return send_from_directory(PAYMENT_PROOF_DIR, path.name, as_attachment=False)


@app.post('/admin/review/<registration_id>')
def admin_review(registration_id):
    gate = admin_required()
    if gate:
        return gate
    action = request.form.get('action', '')
    note = request.form.get('admin_note', '').strip()[:500]
    if action not in {'approve', 'reject'}:
        abort(400)
    conn = get_db()
    row = conn.execute('SELECT * FROM registrations WHERE registration_id = ?', (registration_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    if action == 'approve':
        if not row['payment_reference'] or not row['payment_screenshot_path']:
            conn.close()
            flash('Cannot approve: payment reference and proof must be submitted first.', 'error')
            return redirect(url_for('admin_dashboard'))
        conn.execute("UPDATE registrations SET payment_status = 'Paid', paid_at = ?, admin_note = ? WHERE registration_id = ?",
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), note or 'Manually verified by admin', registration_id))
        flash(f'{registration_id} marked as paid. Confirm the amount in your UPI app/bank before approving.', 'success')
    else:
        conn.execute("UPDATE registrations SET payment_status = 'Rejected', admin_note = ?, paid_at = NULL WHERE registration_id = ?",
                     (note or 'Payment proof rejected. Please contact the organisers.', registration_id))
        flash(f'Payment proof for {registration_id} rejected.', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/success/<registration_id>')
def success(registration_id):
    conn = get_db()
    registration = conn.execute(
        'SELECT * FROM registrations WHERE registration_id = ?',
        (registration_id,)
    ).fetchone()
    conn.close()
    if not registration:
        return render_template('page.html', title='Registration Not Found', content='<p class="lead-dark">The registration ID could not be found.</p>'), 404
    return render_template('success.html', registration=registration)


@app.route('/uploads/ppt/<path:filename>')
def uploaded_ppt(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


@app.errorhandler(413)
def too_large(_error):
    flash('PPT file is too large. Maximum allowed size is 25 MB.', 'error')
    return redirect(url_for('register'))


init_db()

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1')
