PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS admins (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS access_keys (
  id TEXT PRIMARY KEY,
  key_hash TEXT UNIQUE NOT NULL,
  label TEXT,
  plan TEXT DEFAULT 'basic',
  status TEXT DEFAULT 'active',
  expires_at TEXT,
  max_devices INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_activations (
  id TEXT PRIMARY KEY,
  access_key_id TEXT NOT NULL,
  device_hash TEXT NOT NULL,
  activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(access_key_id) REFERENCES access_keys(id),
  UNIQUE(access_key_id, device_hash)
);

CREATE TABLE IF NOT EXISTS login_sessions (
  id TEXT PRIMARY KEY,
  access_key_id TEXT,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(access_key_id) REFERENCES access_keys(id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT,
  action TEXT NOT NULL,
  details TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_keys_status ON access_keys(status);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON login_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_activations_key ON device_activations(access_key_id);
