DROP TABLE IF EXISTS panels;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS choices;
DROP TABLE IF EXISTS allocations;

CREATE TABLE panels (
    id SERIAL PRIMARY KEY,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issue INTEGER NOT NULL,
    page INTEGER NOT NULL,
    panel INTEGER NOT NULL
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discord_username TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE choices (
    id SERIAL PRIMARY KEY,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    u INTEGER,
    panel INTEGER,
    preference INTEGER, -- first, second, or third preference (1/2/3)

    FOREIGN KEY(u) REFERENCES users(id),
    FOREIGN KEY(panel) REFERENCES panels(id)
);


CREATE TABLE allocations (
    id SERIAL PRIMARY KEY,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    u INTEGER,
    panel INTEGER UNIQUE,  -- null if no panels available

    FOREIGN KEY(u) REFERENCES users(id),
    FOREIGN KEY(panel) REFERENCES panels(id)
);

