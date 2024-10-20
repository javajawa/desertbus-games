-- SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
--
-- SPDX-License-Identifier: BSD-2-Clause

create table User
(
    user_id   integer           not null
        constraint user_id
            primary key autoincrement,
    user_name text              not null,
    twitch_id integer           not null,
    is_mod    integer default 0 not null
);


create table Episode
(
    episode_id      integer                           not null
        constraint episode_id
            primary key autoincrement,
    user_id         integer                           not null,
    title           TEXT                              not null,
    description     TEXT                              not null,
    episode_created integer default CURRENT_TIMESTAMP not null,
    game_engine     text
);

create index creator
    on Episode (user_id);

create table EpisodeVersion
(
    episode_id      integer                           not null
        constraint episode
            references Episode,
    version         INTEGER                           not null,
    state           text    default 'DRAFT'           not null,
    version_created integer default CURRENT_TIMESTAMP not null,
    version_updated integer default CURRENT_TIMESTAMP not null,
    data            BLOB                              not null,
    constraint episode_version
        primary key (episode_id, version)
);

create table Blob
(
    blob_id TEXT    not null
        constraint blob
            primary key,
    mime    text    not null,
    width   integer not null,
    height  integer not null
);

create table Notification
(
    notification_id integer                           not null
        constraint notification_id
            primary key autoincrement,
    user_id         integer                           not null
        constraint user
            references User
            on update restrict on delete cascade,
    created_at      INTEGER default CURRENT_TIMESTAMP not null,
    is_read         integer default 0                 not null,
    data            TEXT                              not null
);

create index user_sorted
    on Notification (user_id asc, created_at desc);
