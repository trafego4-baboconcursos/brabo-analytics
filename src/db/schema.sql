-- SQLite schema for analysis system
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  code TEXT NOT NULL,
  FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS launches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  course_id INTEGER NOT NULL,
  code TEXT NOT NULL UNIQUE,
  start_date TEXT,
  end_date TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id),
  FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  launch_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_hash TEXT,
  imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (launch_id) REFERENCES launches(id)
);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  launch_id INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (launch_id) REFERENCES launches(id)
);

CREATE TABLE IF NOT EXISTS metrics_summary (
  snapshot_id INTEGER PRIMARY KEY,
  total_sales INTEGER,
  hotmart_sales INTEGER,
  tmb_sales INTEGER,
  total_revenue REAL,
  fb_spend REAL,
  yt_spend REAL,
  ri_sales INTEGER,
  ri_revenue REAL,
  ri_buyers_with_utm INTEGER,
  ri_buyers_without_utm INTEGER,
  roas REAL,
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS metrics_by_source (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  buyers INTEGER,
  revenue REAL,
  spend REAL,
  roas REAL,
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS utm_top (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  buyers INTEGER,
  revenue REAL,
  payment_card INTEGER,
  payment_boleto INTEGER,
  payment_pix INTEGER,
  payment_other INTEGER,
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS ri_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  section TEXT NOT NULL,
  source TEXT NOT NULL,
  metric TEXT,
  value TEXT,
  buyers INTEGER,
  revenue REAL,
  payment_card INTEGER,
  payment_boleto INTEGER,
  payment_pix INTEGER,
  payment_other INTEGER,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS ri_campaign_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  launch_id INTEGER NOT NULL,
  launch_code TEXT NOT NULL,
  report_html TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  total_sales INTEGER,
  hotmart_sales INTEGER,
  tmb_sales INTEGER,
  total_revenue REAL,
  fb_spend REAL,
  yt_spend REAL,
  ri_sales INTEGER,
  ri_revenue REAL,
  ri_buyers_with_utm INTEGER,
  ri_buyers_without_utm INTEGER,
  roas REAL,
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(id),
  FOREIGN KEY (launch_id) REFERENCES launches(id)
);
