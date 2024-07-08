DROP TABLE IF EXISTS panels;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS choices;

CREATE TABLE panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issue INTEGER NOT NULL,
    page INTEGER NOT NULL,
    panel INTEGER NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discord_username TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_choice INTEGER UNIQUE,
    FOREIGN KEY(confirmed_choice) REFERENCES panels(id)
);

CREATE TABLE choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    from_user INTEGER,
    first_choice INTEGER,
    second_choice INTEGER,
    third_choice INTEGER,
    status TEXT CHECK(status IN ('PENDING', 'PROCESSED')) NOT NULL DEFAULT 'PENDING',
    confirmed_choice INTEGER,

    FOREIGN KEY(from_user) REFERENCES users(id),
    FOREIGN KEY(first_choice) REFERENCES panels(id),
    FOREIGN KEY(second_choice) REFERENCES panels(id),
    FOREIGN KEY(third_choice) REFERENCES panels(id)
    FOREIGN KEY(confirmed_choice) REFERENCES panels(id)
);
