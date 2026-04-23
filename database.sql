DROP TABLE IF EXISTS logs;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(30) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','member') NOT NULL DEFAULT 'member',
    status ENUM('active','banned') NOT NULL DEFAULT 'active',
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    is_online BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL DEFAULT NULL,
    last_seen DATETIME NULL DEFAULT NULL,
    last_login_ip VARCHAR(45) NULL,
    CHECK (CHAR_LENGTH(username) BETWEEN 3 AND 30)
) ENGINE=InnoDB;

CREATE TABLE messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    message VARCHAR(500) NOT NULL,
    sender_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id)
        REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id INT NULL,
    username VARCHAR(30) NULL,
    ip_address VARCHAR(45) NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_log_user FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_users_role_status ON users(role, status);
CREATE INDEX idx_users_status_online ON users(status, is_online);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_sender_created ON messages(sender_id, created_at);
CREATE INDEX idx_logs_created_at ON logs(created_at);
CREATE INDEX idx_logs_user_created ON logs(user_id, created_at);
CREATE INDEX idx_logs_event_created ON logs(event_type, created_at);

-- Default bootstrap admin:
-- username: admin
-- password: AdminPass123!
INSERT INTO users (username, email, password_hash, role, status, is_banned, is_deleted)
VALUES (
    'admin',
    'admin@sentinel.local',
    'scrypt:32768:8:1$WryXFwfi5OkUD5aE$cd5a917f7825f8a334c0317f9aaf505435022b92ba8ae59cb691bf6a596bb566e06b5a8808db6817db7ba51e6d0cc1956059ac8e09b27d23efe0469931e2baf0',
    'admin',
    'active',
    FALSE,
    FALSE
);
