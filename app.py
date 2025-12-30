import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import models
import auth
import openshock

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database on first run
if not os.path.exists(models.DATABASE_PATH):
    models.init_db()

@app.route('/')
@auth.login_required
def index():
    user = auth.get_current_user()
    devices = models.get_devices_by_user(user['id'])
    return render_template('dashboard.html', devices=devices)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = models.get_user_by_username(username)

        if user and auth.check_password(password, user['password_hash']):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password:
            return render_template('register.html', error='Username and password are required')

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')

        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')

        password_hash = auth.hash_password(password)
        user_id = models.create_user(username, password_hash)

        if user_id:
            session['user_id'] = user_id
            return redirect(url_for('index'))
        else:
            return render_template('register.html', error='Username already exists')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
@auth.login_required
def settings():
    user = auth.get_current_user()

    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        had_api_key = bool(user['openshock_api_key'])

        models.update_user_api_key(user['id'], api_key)

        success_message = 'API key updated successfully'

        # Auto-sync if this is the first time adding an API key
        if api_key and not had_api_key:
            sync_success, result = openshock.fetch_user_shockers(api_key)
            if sync_success:
                created, updated, deleted = models.sync_devices_from_openshock(user['id'], result)
                success_message = f'API key saved and devices synced: {created} new, {updated} updated, {deleted} removed'
            else:
                success_message = f'API key saved but sync failed: {result}'

        return render_template('settings.html',
                             success=success_message,
                             api_key=api_key,
                             username=user['username'])

    return render_template('settings.html',
                         api_key=user['openshock_api_key'] or '',
                         username=user['username'])

@app.route('/devices/sync', methods=['POST'])
@auth.login_required
def sync_devices():
    user = auth.get_current_user()

    if not user['openshock_api_key']:
        return jsonify({
            'success': False,
            'message': 'Please configure your OpenShock API key in Settings first'
        }), 400

    # Fetch shockers from OpenShock
    success, result = openshock.fetch_user_shockers(user['openshock_api_key'])

    if not success:
        return jsonify({'success': False, 'message': result}), 400

    # Sync to database
    created, updated, deleted = models.sync_devices_from_openshock(user['id'], result)

    # Get updated device list
    devices = models.get_devices_by_user(user['id'])

    return jsonify({
        'success': True,
        'message': f'Synced: {created} new, {updated} updated, {deleted} removed',
        'devices': [dict(d) for d in devices]
    })

@app.route('/device/update/<int:device_id>', methods=['POST'])
@auth.login_required
def update_device(device_id):
    user = auth.get_current_user()
    data = request.json

    # Convert boolean strings to actual booleans
    if 'enabled' in data:
        data['enabled'] = 1 if data['enabled'] else 0

    models.update_device(device_id, user['id'], **data)
    return jsonify({'success': True})

@app.route('/device/delete/<int:device_id>', methods=['POST'])
@auth.login_required
def delete_device(device_id):
    user = auth.get_current_user()
    models.delete_device(device_id, user['id'])
    return jsonify({'success': True})

@app.route('/devices/reset-intensity', methods=['POST'])
@auth.login_required
def reset_intensity():
    user = auth.get_current_user()
    devices = models.get_devices_by_user(user['id'])

    # Reset current_intensity to 0 for all devices with intensity_increment
    for device in devices:
        if device['intensity_increment']:
            models.update_device(device['id'], user['id'], current_intensity=0)

    return jsonify({'success': True})

@app.route('/device/control/<int:device_id>', methods=['POST'])
@auth.login_required
def control_device(device_id):
    user = auth.get_current_user()
    device = models.get_device(device_id, user['id'])

    if not device:
        return jsonify({'success': False, 'message': 'Device not found'})

    data = request.json
    intensity = data.get('intensity')
    duration = data.get('duration')
    control_type = data.get('control_type', 'Shock')
    use_increment = data.get('use_increment', False)
    increment_after = data.get('increment_after', True)  # Whether to increment after trigger

    # Handle increment mode
    if use_increment and device['intensity_increment']:
        intensity = device['current_intensity']
        # Only increment if increment_after is True
        if increment_after:
            # Calculate next intensity
            next_intensity = intensity + device['intensity_increment']
            if next_intensity > 100:
                next_intensity = 0
            # Update current_intensity for next trigger
            models.update_device(device_id, user['id'], current_intensity=next_intensity)

    success, message = openshock.control_shocker(
        device['shocker_id'],
        user['openshock_api_key'],
        intensity,
        duration,
        control_type
    )

    return jsonify({'success': success, 'message': message, 'current_intensity': intensity if use_increment else None})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
