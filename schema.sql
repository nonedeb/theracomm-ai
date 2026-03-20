create table if not exists users (
    id serial primary key,
    full_name varchar(120) not null,
    email varchar(120) unique not null,
    password_hash varchar(255) not null,
    role varchar(20) not null default 'student',
    section varchar(50),
    specialization varchar(100),
    status varchar(20) not null default 'active',
    created_at timestamp not null default current_timestamp
);

create table if not exists scenarios (
    id serial primary key,
    title varchar(150) not null,
    scenario_type varchar(30) not null default 'chat',
    category varchar(100) not null,
    patient_name varchar(100) not null,
    patient_age integer,
    emotional_state varchar(100) not null,
    clinical_context text not null,
    opening_statement text not null,
    difficulty varchar(30) not null default 'Beginner',
    created_at timestamp not null default current_timestamp
);

create table if not exists attempts (
    id serial primary key,
    user_id integer not null references users(id) on delete cascade,
    scenario_id integer not null references scenarios(id) on delete cascade,
    student_response text not null,
    ai_feedback text not null,
    score integer not null default 0,
    created_at timestamp not null default current_timestamp
);
