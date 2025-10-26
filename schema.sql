CREATE DATABASE IF NOT EXISTS evaluation_system;
USE evaluation_system;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS tbl_evaluation_details;
DROP TABLE IF EXISTS tbl_evaluation;
DROP TABLE IF EXISTS tbl_evaluation_questions;
DROP TABLE IF EXISTS tbl_instructor;
DROP TABLE IF EXISTS tbl_teacher;
DROP TABLE IF EXISTS tbl_student;
DROP TABLE IF EXISTS tbl_admin;

CREATE TABLE tbl_admin (
    a_id       INT          AUTO_INCREMENT PRIMARY KEY,
    a_username VARCHAR(50)  NOT NULL UNIQUE,
    a_password VARCHAR(255) NOT NULL
);

CREATE TABLE tbl_teacher (
    t_id         INT          PRIMARY KEY AUTO_INCREMENT,
    t_username   VARCHAR(50)  UNIQUE NOT NULL,
    t_password   VARCHAR(255) NOT NULL,
    t_first_name VARCHAR(255) NOT NULL,
    t_last_name  VARCHAR(255) NOT NULL
);

CREATE TABLE tbl_instructor (
    i_id         INT          PRIMARY KEY AUTO_INCREMENT,
    i_first_name VARCHAR(255) NOT NULL,
    i_last_name  VARCHAR(255) NOT NULL,
    i_course     VARCHAR(255) NOT NULL,
    t_id         INT, -- Optional link to a tbl_teacher account
    FOREIGN KEY (t_id) REFERENCES tbl_teacher(t_id)
);

CREATE TABLE tbl_evaluation_questions (
    q_id    INT    PRIMARY KEY AUTO_INCREMENT,
    q_text  TEXT   NOT NULL,
    q_order INT    NOT NULL UNIQUE
);

CREATE TABLE tbl_student (
    s_id               INT          PRIMARY KEY AUTO_INCREMENT,
    s_schoolID         VARCHAR(20)  NOT NULL UNIQUE,
    s_password         VARCHAR(255) NOT NULL,
    s_first_name       VARCHAR(255) NOT NULL,
    s_last_name        VARCHAR(255) NOT NULL,
    s_email            VARCHAR(255) NOT NULL UNIQUE,
    s_year_level       VARCHAR(50)  NOT NULL,
    s_status           VARCHAR(20)  NOT NULL, 
    s_date_registered  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tbl_evaluation (
    e_id             INT          PRIMARY KEY AUTO_INCREMENT,
    i_id             INT          NOT NULL,
    s_schoolID       VARCHAR(20)  NOT NULL,
    remarks          TEXT,
    e_date_submitted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (i_id) REFERENCES tbl_instructor(i_id),
    FOREIGN KEY (s_schoolID) REFERENCES tbl_student(s_schoolID),
    UNIQUE KEY unique_evaluation (i_id, s_schoolID)
);

CREATE TABLE tbl_evaluation_details (
    ed_id         INT PRIMARY KEY AUTO_INCREMENT,
    e_id          INT NOT NULL,
    q_id          INT NOT NULL,
    rating_value  INT NOT NULL, -- Rating from 1 to 5
    FOREIGN KEY (e_id) REFERENCES tbl_evaluation(e_id) ON DELETE CASCADE,
    FOREIGN KEY (q_id) REFERENCES tbl_evaluation_questions(q_id)
);

INSERT INTO tbl_admin (a_username, a_password) VALUES
('admin', 'password');

INSERT INTO tbl_evaluation_questions (q_text, q_order) VALUES
('Subject matter knowledge and expertise.', 1),
('Clarity of explanations and organization of lessons.', 2),
('Fairness and helpfulness in providing feedback.', 3),
('Overall effectiveness as an instructor.', 4);

INSERT INTO tbl_teacher (t_username, t_password, t_first_name, t_last_name)
VALUES
('ching', 'password', 'Ching', 'Archival'),
('rose', 'password', 'Rose', 'Gamboa');

INSERT INTO tbl_instructor (i_first_name, i_last_name, i_course, t_id)
VALUES
('Ching', 'Archival', 'OOP 1', 1),
('Rose', 'Gamboa', 'Data Structures', 2);

INSERT INTO tbl_student 
(s_schoolID, s_password, s_first_name, s_last_name, s_email, s_year_level, s_status)
VALUES
('12345', 'password', 'Test', 'Student', 'test@example.com', '4th Year', 'Approved');