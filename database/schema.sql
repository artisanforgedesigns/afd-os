CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    openshock_api_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,

    -- OpenShock identifiers
    shocker_id TEXT NOT NULL,
    device_name TEXT,
    shocker_name TEXT,

    -- User customizable fields
    nickname TEXT NOT NULL,
    frequency_min INTEGER,
    frequency_max INTEGER,
    intensity_min INTEGER,
    intensity_max INTEGER,
    intensity_increment INTEGER,
    current_intensity INTEGER DEFAULT 0,
    duration_min INTEGER,
    duration_max INTEGER,
    enabled BOOLEAN DEFAULT 0,
    display_order INTEGER DEFAULT 0,

    -- Sync metadata
    is_online BOOLEAN DEFAULT 1,
    is_paused BOOLEAN DEFAULT 0,
    last_synced TIMESTAMP,

    -- Pre-vibration warning
    pre_vibrate_enabled BOOLEAN DEFAULT 0,
    pre_vibrate_duration INTEGER DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_user_shocker ON devices(user_id, shocker_id);
CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);
CREATE INDEX IF NOT EXISTS idx_devices_display_order ON devices(display_order);
