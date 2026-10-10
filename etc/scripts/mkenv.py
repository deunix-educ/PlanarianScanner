#!/usr/bin/env python3
"""Génère test_tube_scanner/.env à partir de .env.example selon le mode.

usage: mkenv.py dev|prod [--force] [--hostname scanner]
Ne remplace jamais un .env existant sans --force.
"""
import argparse
import getpass
import re
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "test_tube_scanner"


def rand(n=24):
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "prod"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hostname", default="scanner")
    a = ap.parse_args()

    env = APP / ".env"
    if env.exists() and not a.force:
        print(f"{env} existe déjà (utiliser --force pour le régénérer) : inchangé")
        return 0

    datas = ROOT / "datas"
    user = getpass.getuser()
    host = a.hostname
    over = {
        "USER": user,
        "GROUP": user,
        "SECRET_KEY": '"' + secrets.token_urlsafe(50) + '"',
        "DOMAIN_SERVER": f"{host}.local",
        "EXPORTS_LOCAL_PATH": datas / "exports",
        "EXPORT_REMOTE_PATH": datas / "remote" / "exports",
        "REDUCTSTORE_PATH": datas / "reduct-media",
        "CSV_EXPORT_DIR": datas / "exports" / "csv",
        "BACKUP_DIR": datas / "backup" / "mariadb",
        "REDUCTSTORE_TOKEN": "scanner-" + secrets.token_hex(16),
    }
    if a.mode == "dev":
        over.update(DEBUG="True", SQLITE3="default", MARIADB="None",
                    SQLITE3_PATH=str(datas) + "/", GRBL_SIMULATION="True")
    else:
        pw = rand()
        over.update(DEBUG="False", SQLITE3="None", MARIADB="default", GRBL_SIMULATION="False",
                    DATABASE_PASSWORD=pw, DATABASE_ROOT_PASSWORD=rand(),
                    SUPERADMIN_PASS=rand(12))

    out = []
    for line in (APP / ".env.example").read_text().splitlines():
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in over:
            line = f"{m.group(1)}={over.pop(m.group(1))}"
        out.append(line)
    out.append("")
    out.append(f"# --- ajouté par mkenv.py ({a.mode})")
    for k, v in over.items():
        out.append(f"{k}={v}")
    env.write_text("\n".join(out) + "\n")
    env.chmod(0o600)
    print(f"{env} créé (mode {a.mode})")
    if a.mode == "prod":
        print("  -> mots de passe générés : relire le fichier (SUPERADMIN_PASS, DATABASE_*)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
