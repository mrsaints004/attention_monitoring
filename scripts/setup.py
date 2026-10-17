"""Create local config without overwriting existing credentials."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
backend = root / 'backend' / '.env'
if not backend.exists():
    text = (backend.parent / '.env.example').read_text().replace('replace-with-a-long-random-secret', secrets.token_urlsafe(48))
    backend.write_text(text)
    backend.chmod(0o600)
elif not any(line.startswith('AUTH_SECRET=') for line in backend.read_text().splitlines()):
    with backend.open('a') as output:
        output.write('\nAUTH_SECRET=' + secrets.token_urlsafe(48) + '\n')
frontend = root / 'frontend' / '.env.local'
if not frontend.exists():
    frontend.write_text((frontend.parent / '.env.example').read_text())
print('Local environment files ready. Existing configuration preserved.')
