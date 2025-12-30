import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'database', 'afd.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with schema"""
    schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
    conn = get_db()
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

# User operations
def create_user(username, password_hash):
    conn = get_db()
    try:
        cursor = conn.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def update_user_api_key(user_id, api_key):
    conn = get_db()
    conn.execute('UPDATE users SET openshock_api_key = ? WHERE id = ?', (api_key, user_id))
    conn.commit()
    conn.close()

# Device operations
def get_devices_by_user(user_id):
    conn = get_db()
    devices = conn.execute(
        'SELECT * FROM devices WHERE user_id = ? ORDER BY display_order, created_at',
        (user_id,)
    ).fetchall()
    conn.close()
    return devices

def create_device(user_id, shocker_id, device_name, shocker_name, is_online=True, is_paused=False):
    conn = get_db()
    max_order = conn.execute(
        'SELECT MAX(display_order) as max_order FROM devices WHERE user_id = ?',
        (user_id,)
    ).fetchone()['max_order']
    next_order = (max_order or 0) + 1
    current_time = datetime.now().isoformat()

    cursor = conn.execute('''
        INSERT INTO devices (
            user_id, shocker_id, device_name, shocker_name, nickname,
            is_online, is_paused, last_synced, display_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, shocker_id, device_name, shocker_name, shocker_name,
        is_online, is_paused, current_time, next_order
    ))
    conn.commit()
    device_id = cursor.lastrowid
    conn.close()
    return device_id

def update_device(device_id, user_id, **kwargs):
    """Update device fields. Only updates provided kwargs."""
    allowed_fields = [
        'nickname', 'frequency_min', 'frequency_max',
        'intensity_min', 'intensity_max', 'intensity_increment', 'current_intensity',
        'duration_min', 'duration_max',
        'enabled', 'display_order',
        'device_name', 'shocker_name', 'is_online', 'is_paused', 'last_synced',
        'pre_vibrate_enabled', 'pre_vibrate_duration'
    ]

    fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not fields:
        return False

    set_clause = ', '.join(f'{k} = ?' for k in fields.keys())
    values = list(fields.values()) + [device_id, user_id]

    conn = get_db()
    conn.execute(
        f'UPDATE devices SET {set_clause} WHERE id = ? AND user_id = ?',
        values
    )
    conn.commit()
    conn.close()
    return True

def delete_device(device_id, user_id):
    conn = get_db()
    conn.execute('DELETE FROM devices WHERE id = ? AND user_id = ?', (device_id, user_id))
    conn.commit()
    conn.close()

def get_device(device_id, user_id):
    conn = get_db()
    device = conn.execute(
        'SELECT * FROM devices WHERE id = ? AND user_id = ?',
        (device_id, user_id)
    ).fetchone()
    conn.close()
    return device

def sync_devices_from_openshock(user_id, shockers_data):
    """
    Sync devices from OpenShock API data

    Args:
        user_id: User ID
        shockers_data: List of shocker dicts from OpenShock API

    Returns:
        tuple: (created_count: int, updated_count: int, deleted_count: int)
    """
    conn = get_db()
    created = 0
    updated = 0
    deleted = 0
    current_time = datetime.now().isoformat()

    # Get existing devices for this user
    existing = conn.execute(
        'SELECT shocker_id, id FROM devices WHERE user_id = ?',
        (user_id,)
    ).fetchall()
    existing_map = {row['shocker_id']: row['id'] for row in existing}

    # Track which shocker_ids are in the API response
    api_shocker_ids = set()

    for shocker in shockers_data:
        shocker_id = shocker.get('id')
        device_name = shocker.get('device', {}).get('name', 'Unknown Device')
        shocker_name = shocker.get('name', 'Unnamed Shocker')
        is_paused = shocker.get('isPaused', False)
        is_online = shocker.get('device', {}).get('online', True)

        # Skip if this looks like a hub instead of a shocker
        if not shocker_id or device_name == 'Unknown Device' or not device_name:
            continue

        api_shocker_ids.add(shocker_id)

        if shocker_id in existing_map:
            # Update existing device (only read-only fields)
            conn.execute('''
                UPDATE devices
                SET device_name = ?, shocker_name = ?, is_online = ?, is_paused = ?, last_synced = ?
                WHERE id = ? AND user_id = ?
            ''', (device_name, shocker_name, is_online, is_paused, current_time, existing_map[shocker_id], user_id))
            updated += 1
        else:
            # Create new device with defaults
            max_order = conn.execute(
                'SELECT MAX(display_order) as max_order FROM devices WHERE user_id = ?',
                (user_id,)
            ).fetchone()['max_order']
            next_order = (max_order or 0) + 1

            conn.execute('''
                INSERT INTO devices (
                    user_id, shocker_id, device_name, shocker_name,
                    nickname, is_online, is_paused, last_synced, display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, shocker_id, device_name, shocker_name,
                shocker_name,  # Default nickname to shocker name
                is_online, is_paused, current_time, next_order
            ))
            created += 1

    # Delete devices that no longer exist in the API response
    for shocker_id in existing_map.keys():
        if shocker_id not in api_shocker_ids:
            conn.execute(
                'DELETE FROM devices WHERE shocker_id = ? AND user_id = ?',
                (shocker_id, user_id)
            )
            deleted += 1

    conn.commit()
    conn.close()
    return created, updated, deleted
