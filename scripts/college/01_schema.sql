-- A second, unrelated schema. The guardrail is pointed at it only by changing DB_NAME.
CREATE TABLE faculty (
    faculty_id  SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    dept        TEXT NOT NULL,
    designation TEXT,
    salary      NUMERIC(10,2)
);

CREATE TABLE students (
    student_id     SERIAL PRIMARY KEY,
    full_name      TEXT NOT NULL,
    email          TEXT NOT NULL,
    phone          TEXT,
    dept           TEXT NOT NULL,
    admission_year INT,
    cgpa           NUMERIC(4,2)
);

CREATE TABLE courses (
    course_id  SERIAL PRIMARY KEY,
    title      TEXT NOT NULL,
    dept       TEXT NOT NULL,
    credits    INT,
    faculty_id INT REFERENCES faculty(faculty_id)
);

CREATE TABLE enrollments (
    enrollment_id SERIAL PRIMARY KEY,
    student_id    INT REFERENCES students(student_id),
    course_id     INT REFERENCES courses(course_id),
    semester      TEXT,
    grade         TEXT
);

CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    enrollment_id INT REFERENCES enrollments(enrollment_id),
    class_date    DATE,
    present       BOOLEAN
);

COMMENT ON COLUMN students.email IS 'PII: student email';
COMMENT ON COLUMN students.phone IS 'PII: student phone';
COMMENT ON COLUMN faculty.salary IS 'sensitive: payroll';
