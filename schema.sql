DROP TABLE IF EXISTS panels;
DROP TABLE IF EXISTS users;

CREATE TABLE panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    page INTEGER NOT NULL,
    panel INTEGER NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discord_username TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    first_choice INTEGER,
    second_choice INTEGER,
    third_choice INTEGER,
    status TEXT CHECK(status IN ('READY', 'TO_PROCESS', 'FIXED')) NOT NULL DEFAULT 'READY', -- READY - confirmed_choice is ready to be chosen; TO_PROCESS - user has submitted the selection form, automated process needs to run; FIXED - confirmed_choice is final.
    confirmed_choice INTEGER UNIQUE,
    FOREIGN KEY(confirmed_choice) REFERENCES panels(id)
);
