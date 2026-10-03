-- PostgreSQL-ready core schema (SQLite migration is created by SQLAlchemy).
CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, college VARCHAR(160), course VARCHAR(120), year INTEGER, avatar VARCHAR(10), goals TEXT, styles TEXT, duration INTEGER DEFAULT 90, group_size INTEGER DEFAULT 4, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE subjects (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE topics (id SERIAL PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id), name VARCHAR(120) NOT NULL);
CREATE TABLE user_subjects (user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, subject_id INTEGER REFERENCES subjects(id), level VARCHAR(30), PRIMARY KEY(user_id,subject_id));
CREATE TABLE availability (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, day VARCHAR(15), start_hour INTEGER, end_hour INTEGER);
CREATE TABLE connections (id SERIAL PRIMARY KEY, sender_id INTEGER REFERENCES users(id), recipient_id INTEGER REFERENCES users(id), status VARCHAR(20) DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE study_groups (id SERIAL PRIMARY KEY, name VARCHAR(140), description TEXT, subject VARCHAR(100), goal VARCHAR(100), max_members INTEGER, privacy VARCHAR(20), created_by INTEGER REFERENCES users(id));
CREATE TABLE group_members (group_id INTEGER REFERENCES study_groups(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id), PRIMARY KEY(group_id,user_id));
CREATE TABLE tasks (id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES study_groups(id) ON DELETE CASCADE, title VARCHAR(200), description TEXT, assignee_id INTEGER REFERENCES users(id), deadline DATE, priority VARCHAR(20), status VARCHAR(30) DEFAULT 'To Do');
CREATE TABLE sessions (id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES study_groups(id) ON DELETE CASCADE, title VARCHAR(160), topic VARCHAR(120), starts_at TIMESTAMP, ends_at TIMESTAMP, meeting_link TEXT);
CREATE TABLE session_members (session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id), rsvp VARCHAR(20), PRIMARY KEY(session_id,user_id));
CREATE TABLE resources (id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES study_groups(id) ON DELETE CASCADE, title VARCHAR(160), url TEXT, type VARCHAR(40));
CREATE TABLE messages (id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES study_groups(id) ON DELETE CASCADE, sender_id INTEGER REFERENCES users(id), content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, type VARCHAR(40), content TEXT, read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX idx_connections_recipient ON connections(recipient_id,status); CREATE INDEX idx_tasks_group ON tasks(group_id); CREATE INDEX idx_availability_user ON availability(user_id);
