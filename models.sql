CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS trainings (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    limit_count INTEGER
);

CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    training_id INTEGER REFERENCES trainings(id),
    status TEXT DEFAULT 'active',
    UNIQUE (user_id, training_id)
);

CREATE TABLE IF NOT EXISTS waitlist (
    id SERIAL PRIMARY KEY,
    training_id INTEGER REFERENCES trainings(id),
    user_id INTEGER REFERENCES users(id),
    position INTEGER,
    notified BOOLEAN DEFAULT FALSE
);
