CREATE DATABASE IF NOT EXISTS evaluation_system;
USE evaluation_system;

DROP TABLE IF EXISTS tbl_evaluation;
DROP TABLE IF EXISTS tbl_instructor;
DROP TABLE IF EXISTS tbl_student;

CREATE TABLE tbl_student (
    s_id INT PRIMARY KEY AUTO_INCREMENT,
    s_schoolID VARCHAR(255) UNIQUE NOT NULL,
    s_first_name VARCHAR(255) NOT NULL,
    s_last_name VARCHAR(255) NOT NULL,
    s_email VARCHAR(255) UNIQUE NOT NULL,
    s_year_level VARCHAR(50) NOT NULL,
    s_status VARCHAR(50) NOT NULL DEFAULT 'Pending' 
);

CREATE TABLE tbl_instructor (
    i_id INT PRIMARY KEY AUTO_INCREMENT,
    i_first_name VARCHAR(255) NOT NULL,
    i_last_name VARCHAR(255) NOT NULL,
    i_course VARCHAR(255) NOT NULL
);

CREATE TABLE tbl_evaluation (
    e_id INT PRIMARY KEY AUTO_INCREMENT,
    i_id INT NOT NULL,
    s_schoolID VARCHAR(255) NOT NULL,
    e_rating FLOAT NOT NULL,
    e_remarks TEXT,
    e_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (i_id) REFERENCES tbl_instructor(i_id),
    FOREIGN KEY (s_schoolID) REFERENCES tbl_student(s_schoolID)
);

INSERT INTO tbl_instructor (i_first_name, i_last_name, i_course) 
VALUES ('Ching', 'Archival', 'OOP 1');
INSERT INTO tbl_instructor (i_first_name, i_last_name, i_course) 
VALUES ('Rose', 'Gamboa', 'Data Structures');

INSERT INTO tbl_student (s_schoolID, s_first_name, s_last_name, s_email, s_year_level, s_status) 
VALUES ('12345', 'John', 'Doe', 'john.doe@school.edu', '2nd Year', 'Approved');

INSERT INTO tbl_student (s_schoolID, s_first_name, s_last_name, s_email, s_year_level, s_status) 
VALUES ('67890', 'Jane', 'Smith', 'jane.smith@school.edu', '1st Year', 'Pending');
