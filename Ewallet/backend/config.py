import os
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env")
DB_PATH = BASE_DIR / "instance" / "finance.db"
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-key")
VAULT_KEY = os.getenv("VAULT_KEY")
if not VAULT_KEY:
    key_file = BASE_DIR / "instance" / "vault.key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        VAULT_KEY = key_file.read_text().strip()
    else:
        VAULT_KEY = Fernet.generate_key().decode()
        key_file.write_text(VAULT_KEY)
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
