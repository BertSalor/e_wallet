# Installation guide
1. Install Python 3.10+.
2. From the project root run `py -m venv .venv`.
3. Activate: `\.venv\Scripts\Activate.ps1` (PowerShell).
4. Install: `python -m pip install -r backend/requirements.txt`.
5. Copy `.env.example` to `.env` and set a long random `SECRET_KEY`; set a persistent Fernet `VAULT_KEY` for deployments.
6. Run `python run.py`; open http://127.0.0.1:5000.


### Create an administrator

After installing dependencies and initializing the application, run `cd backend` then `python create_admin.py`. Follow the prompts to create the first administrator. Open `/admin.html` after signing in.
