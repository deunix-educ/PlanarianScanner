'''
Created on 18 mai 2026

@author: denis
'''
from celery import shared_task

from .services import mariadb_backup


@shared_task
def backup_mariadb_task():
    path = mariadb_backup()

    return {
        "status": "ok",
        "backup": path,
    }