import requests

API_BASE_URL = 'https://api.openshock.app'
USER_AGENT = 'AFD-OpenShock-App/1.0'

def fetch_user_shockers(api_key):
    """
    Fetch user's shockers from OpenShock API

    Args:
        api_key: User's OpenShock API key

    Returns:
        tuple: (success: bool, data: list or error_message: str)
    """
    if not api_key:
        return False, 'OpenShock API key not configured'

    headers = {
        'User-Agent': USER_AGENT,
        'Open-Shock-Token': api_key
    }

    try:
        # First, get all devices (hubs)
        devices_url = f'{API_BASE_URL}/1/devices'
        devices_response = requests.get(devices_url, headers=headers, timeout=10)

        if devices_response.status_code == 401:
            return False, 'Invalid API key'
        elif devices_response.status_code != 200:
            return False, f'API error getting devices: {devices_response.status_code}'

        devices_data = devices_response.json().get('data', [])

        # Now get shockers for each device
        all_shockers = []
        for device in devices_data:
            device_id = device.get('id')
            if not device_id:
                continue

            shockers_url = f'{API_BASE_URL}/1/devices/{device_id}/shockers'
            shockers_response = requests.get(shockers_url, headers=headers, timeout=10)

            if shockers_response.status_code == 200:
                shockers = shockers_response.json().get('data', [])
                # Add device info to each shocker
                for shocker in shockers:
                    shocker['device'] = device
                    all_shockers.append(shocker)

        return True, all_shockers

    except requests.exceptions.Timeout:
        return False, 'Request timed out'
    except requests.exceptions.ConnectionError:
        return False, 'Connection error'
    except Exception as e:
        return False, f'Unexpected error: {str(e)}'


def control_shocker(shocker_id, api_key, intensity, duration, control_type='Shock'):
    """
    Send control command to OpenShock shocker directly

    Args:
        shocker_id: OpenShock shocker ID
        api_key: User's OpenShock API key
        intensity: Power level 0-100
        duration: Duration in milliseconds (300-30000)
        control_type: Control type - 'Shock', 'Vibrate', or 'Sound'

    Returns:
        tuple: (success: bool, message: str)
    """
    if not api_key:
        return False, 'OpenShock API key not configured. Please add it in Settings.'

    if not shocker_id:
        return False, 'Shocker ID is required'

    # Validate parameters
    try:
        intensity = int(intensity)
        duration = int(duration)
    except (ValueError, TypeError):
        return False, 'Invalid intensity or duration value'

    if not (0 <= intensity <= 100):
        return False, 'Intensity must be between 0 and 100'

    if not (300 <= duration <= 30000):
        return False, 'Duration must be between 300 and 30000 milliseconds'

    url = f'{API_BASE_URL}/1/shockers/control'
    headers = {
        'User-Agent': USER_AGENT,
        'Open-Shock-Token': api_key,
        'Content-Type': 'application/json'
    }

    payload = [
        {
            'id': shocker_id,
            'type': control_type,
            'intensity': intensity,
            'duration': duration,
            'exclusive': True
        }
    ]

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            return True, 'Shocker triggered successfully'
        elif response.status_code == 404:
            return False, 'Shocker not found or access denied'
        elif response.status_code == 401 or response.status_code == 403:
            return False, 'Invalid API key or access forbidden'
        else:
            # Include response body for debugging
            error_detail = response.text[:200] if response.text else 'No details'
            return False, f'API error {response.status_code}: {error_detail}'

    except requests.exceptions.Timeout:
        return False, 'Request timed out. Device may be unreachable.'
    except requests.exceptions.ConnectionError:
        return False, 'Connection error. Check your internet connection.'
    except Exception as e:
        return False, f'Unexpected error: {str(e)}'
