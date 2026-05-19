'''
Created on 18 mai 2026

@author: denis
'''
from pathlib import Path
from datetime import datetime
import subprocess
import gzip
import shutil

from django.conf import settings

BACKUP_DIR = Path(settings.BACKUP_DIR)


def mariadb_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    db = settings.DATABASES["default"]

    db_name = db["NAME"]
    db_user = db["USER"]
    db_password = db["PASSWORD"]
    db_host = db.get("HOST", "localhost")
    db_port = str(db.get("PORT", 3306))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    sql_file = BACKUP_DIR / f"{db_name}_{timestamp}.sql"
    gz_file = BACKUP_DIR / f"{db_name}_{timestamp}.sql.gz"

    cmd = [
        "mariadb-dump",
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        "-h", db_host,
        "-P", db_port,
        "-u", db_user,
        f"-p{db_password}",
        db_name,
    ]

    with open(sql_file, "wb") as f:
        result = subprocess.run(
            cmd,
            stdout=f,
            stderr=subprocess.PIPE,
            check=True,
        )

    with open(sql_file, "rb") as f_in:
        with gzip.open(gz_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    sql_file.unlink()

    return str(gz_file)

