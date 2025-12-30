import bcrypt
from functools import wraps
from flask import session, redirect, url_for
import models

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, password_hash):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Check if user still exists in database
        user = models.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the currently logged-in user"""
    if 'user_id' in session:
        return models.get_user_by_id(session['user_id'])
    return None
