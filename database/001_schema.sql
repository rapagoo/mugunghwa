CREATE DATABASE IF NOT EXISTS mugunghwa CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mugunghwa;
CREATE TABLE IF NOT EXISTS games (
    id VARCHAR(64) PRIMARY KEY,
    phase VARCHAR(32) NOT NULL,
    started_at VARCHAR(32),
    remaining_seconds INT UNSIGNED,
    updated_at VARCHAR(32) NOT NULL,
    authority VARCHAR(16) NOT NULL CHECK(authority='PI'),
    is_test BOOLEAN NOT NULL DEFAULT FALSE,
    INDEX latest_game(updated_at,id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS participants (
    game_id VARCHAR(64) NOT NULL,
    id VARCHAR(64) NOT NULL,
    name VARCHAR(128),
    status VARCHAR(16) NOT NULL CHECK(status IN ('playing','passed','failed')),
    updated_at VARCHAR(32) NOT NULL,
    PRIMARY KEY(game_id,id),
    FOREIGN KEY(game_id) REFERENCES games(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    event_key VARCHAR(128) NOT NULL UNIQUE,
    kind VARCHAR(32) NOT NULL,
    participant_id VARCHAR(64),
    occurred_at VARCHAR(32) NOT NULL,
    FOREIGN KEY(game_id) REFERENCES games(id),
    INDEX game_events(game_id,id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS device_status (
    id VARCHAR(32) PRIMARY KEY,
    connection_state VARCHAR(16) NOT NULL CHECK(connection_state IN ('connected','disconnected','unknown')),
    last_seen_at VARCHAR(32),
    last_command VARCHAR(128),
    last_ack VARCHAR(128),
    updated_at VARCHAR(32) NOT NULL
) ENGINE=InnoDB;
