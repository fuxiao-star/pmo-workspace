CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, code_hash TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, project_kind TEXT NOT NULL DEFAULT 'service');
CREATE TABLE reports (id TEXT PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id), submission_key TEXT NOT NULL, report_date TEXT NOT NULL, period TEXT NOT NULL, project TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(group_id,submission_key));
CREATE INDEX reports_created ON reports(created_at DESC);
CREATE TABLE team_members (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, code_hash TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('owner','member')));
CREATE TABLE team_sessions (token_hash TEXT PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES team_members(id), csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE INDEX sessions_expiry ON team_sessions(expires_at);
CREATE TABLE auth_failures (key TEXT PRIMARY KEY, started_at INTEGER NOT NULL, attempts INTEGER NOT NULL);
