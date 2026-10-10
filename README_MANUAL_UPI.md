# CIVILATHON — manual UPI payment verification

This version replaces Razorpay checkout with UPI payment instructions and manual proof review.

## Payment flow
1. Participant registers and uploads the PPT/PPTX.
2. The app creates a registration and opens `/payment/<registration_id>`.
3. Participant pays the displayed fee to the configured UPI ID, enters the UPI transaction/reference ID, and uploads a payment screenshot (PNG/JPG/WEBP) or PDF (max 8 MB).
4. Status changes to `Pending Verification`.
5. An organiser signs in at `/admin/login`, checks the payment against the receiving UPI/bank account, views the proof, and approves or rejects it.
6. Approval changes status to `Paid`; rejection changes it to `Rejected` and allows the participant to resubmit proof.

## Configuration
Set these environment variables on the Python backend:
- `FLASK_SECRET_KEY`: long random secret; do not commit it.
- `CIVILATHON_ADMIN_PASSWORD`: strong unique admin password.
- `CIVILATHON_UPI_ID`: receiving UPI ID (currently `9713559328@axl`).
- `FLASK_DEBUG=0` in production.

## QR image
Place the organiser-provided QR image at `static/images/payment-qr.png`. The payment page will show a placeholder notice until the file exists. Confirm the QR resolves to the same intended recipient before publishing.

## Run locally
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY='a-long-random-local-secret'
export CIVILATHON_ADMIN_PASSWORD='set-a-strong-password'
export CIVILATHON_UPI_ID='9713559328@axl'
python app.py
```
Open `http://127.0.0.1:5000`; organiser dashboard is at `/admin/login`.

## Important deployment limitations
This update retains the original SQLite database and local filesystem uploads to avoid a destructive rewrite. On hosts with ephemeral filesystems, database changes and uploaded PPT/proof files may be lost during redeploy/restart. Before accepting public registrations, move SQLite to managed PostgreSQL and both PPT and payment-proof files to persistent object storage (or a host with a persistent disk), then test backups and restore. Netlify does not run this Flask app as a persistent Python web server; deploy the Flask backend separately on a Python-capable host and use Netlify for a frontend only if needed.

Manual screenshot verification is not automatic payment verification. Always confirm the amount and transaction in the receiving UPI app/bank statement before approving. Keep the admin password private and do not expose `/admin` to participants.
