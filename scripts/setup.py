"""Generate local credentials once. No passwords or keys are printed or committed."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dest = root / ".env"
if dest.exists():
    print(".env already exists; no values changed.")
else:
    text = (root / ".env.example").read_text()
    for old in [
        "change-this-demo-password",
        "local-demo-only-change-this-32-character-secret",
        "local-demo-device-key-change-this",
    ]:
        text = text.replace(old, secrets.token_urlsafe(32))
    text += "\nPOSTGRES_PASSWORD=" + secrets.token_hex(16) + "\n"
    dest.write_text(text)
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    print(
        "Created .env with random local credentials. Read ADMIN_USERNAME/ADMIN_PASSWORD there to sign in."
    )
print("Next: docker compose --profile demo up --build -d")
