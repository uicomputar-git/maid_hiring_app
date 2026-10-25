# Maid Hiring App (Flask + SQLite)

A local starter application for connecting domestic workers and employers. It includes registration, login, maid search/filtering, hiring requests, favourites, reviews, reports, private maid-employer chat conversations per hiring request, and a role-protected admin page.

## Architecture

- **Flask** serves routes and HTML templates.
- **SQLAlchemy** models users, maid/employer profiles, skills, hiring requests, favourites, reviews and reports.
- **SQLite** stores data in `instance/app.db`.
- **Jinja + Bootstrap 5** renders responsive pages.
- **Flask-WTF CSRFProtect** protects POST forms; Werkzeug securely hashes passwords.

### Database relationships

- `users` has one optional `maid_profiles` or `employer_profiles` record, depending on role.
- `maid_profiles` and `skills` have a many-to-many relationship through `maid_skills`.
- `hiring_requests` links one employer user to one maid user.
- `favourites` links employer and maid users; the pair is unique.
- `reviews` links an employer, maid and one completed hiring request.
- `reports` records a reporter, reported user and reason.
- `chat_messages` stores messages tied to a hiring request and sender; only the two participants can open that conversation. Chats are writable while requests are Pending or Accepted and read-only after the request closes.

## Windows 10/11 setup (Visual Studio Code)

1. Install Python 3.11+ and Visual Studio Code with the Python extension.
2. Extract the project ZIP and open the `maid_hiring_app` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.
5. Install packages:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
6. Initialize tables and skills:

   ```powershell
   flask --app app init-db
   ```
7. Optional demo data:

   ```powershell
   flask --app app seed-demo
   ```

   The seed command also creates a sample Pending hiring request and two example chat messages between the demo maid and employer. Log in with either account and open **Messages** to see the demo conversation.

   Demo login (for local testing only):
   - Maid: `maid@example.com` / `DemoPass123!`
   - Employer: `employer@example.com` / `DemoPass123!`
   - Admin: `admin@example.com` / `AdminPass123!`

8. Start the app:

   ```powershell
   python app.py
   ```

9. Open `http://127.0.0.1:5000`.

## Environment variables

Before deployment, set a strong secret key. In PowerShell for the current terminal:

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
$env:FLASK_DEBUG = "0"
```

For production use HTTPS, set `COOKIE_SECURE=1`, configure a production WSGI server, backups, logging, rate limiting, email/OTP delivery and a real account recovery flow. Do not use the demo accounts on a public server.

## Chat feature

Maid and employer can open **Messages** from the navigation bar or use **Open chat** on a hiring request. Run `python -m flask --app app seed-demo` to create the demo conversation if you don't see any requests. Messages are stored in SQLite and only the maid/employer attached to that request can view them. Messages can be sent while a request is Pending or Accepted; closed requests retain read-only history. The chat checks for new messages every few seconds while the conversation page is open; it uses lightweight polling rather than WebSockets.

## Tests

With the virtual environment active:

```powershell
pytest -q
```

## Notes / production checklist

- This is a functional starter/demo, not a fully audited production service.
- Password reset is not wired to email/SMS because that requires a trusted delivery provider. Do not add an insecure "reset by mobile number only" route.
- Login throttling, OTP, account deactivation UI, email verification, image malware scanning and full admin report handling should be added before public launch.
- Complete addresses and phone numbers are not shown on public maid profiles. Share contact details only through a deliberate, consent-based workflow.
- The admin account is created only by the seed command in this demo. Remove seed credentials and create admin users securely for deployment.


## Always-available direct chat (updated)

- Maid and employer users can message each other without a hiring request.
- Maids can message other maids; employers can message other employers.
- Conversations remain writable after hiring requests are completed, rejected, or cancelled.
- Use **Messages → New chat**, search users by name/email and select **Message**.
- New direct conversation tables (`direct_conversations`, `direct_messages`) are created automatically at startup.
- The older request-specific chat remains available in the inbox for existing hiring requests.
