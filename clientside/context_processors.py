# your_app/context_processors.py
from django.db import connection
from django.db.utils import OperationalError

def database_connection_status(request):
    db_connected = True
    try:
        connection.ensure_connection()
    except OperationalError:
        db_connected = False
    
    return {
        'db_connected': db_connected
    }