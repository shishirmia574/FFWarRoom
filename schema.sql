CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    is_banned INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    time TEXT NOT NULL,
    entry_fee INTEGER,
    prize_pool TEXT,
    status TEXT DEFAULT 'Upcoming'
);

CREATE TABLE participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tournament_id INTEGER,
    team_name TEXT,
    uid TEXT,
    approved INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
);
