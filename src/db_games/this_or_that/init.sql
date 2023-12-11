CREATE TABLE IF NOT EXISTS ThisOrThatGame (
    ident INTEGER PRIMARY KEY,
    this TEXT,
    that TEXT,
    description TEXT,
    credits TEXT
);
CREATE TABLE IF NOT EXISTS ThisOrThatQuestion (
    ident INTEGER,
    question INTEGER PRIMARY KEY,

    prompt TEXT,
    image TEXT,
    info TEXT,

    is_this BOOLEAN,
    is_that BOOEAN,

    UNIQUE (ident, prompt),
    FOREIGN KEY (ident) REFERENCES ThisOrThatGame(ident)
);
