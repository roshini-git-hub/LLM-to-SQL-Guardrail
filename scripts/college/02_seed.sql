SELECT setseed(0.42);

INSERT INTO faculty (full_name, dept, designation, salary)
SELECT 'Faculty ' || g,
       (ARRAY['CSE','ECE','MECH','CIVIL','MBA'])[1 + (g % 5)],
       (ARRAY['Assistant Professor','Associate Professor','Professor'])[1 + floor(random()*3)::int],
       round((60000 + random()*140000)::numeric, 2)
FROM generate_series(1, 60) g;

INSERT INTO students (full_name, email, phone, dept, admission_year, cgpa)
SELECT 'Student ' || g,
       'student' || g || '@college.example',
       '9' || lpad((random()*999999999)::int::text, 9, '0'),
       (ARRAY['CSE','ECE','MECH','CIVIL','MBA'])[1 + floor(random()*5)::int],
       2021 + floor(random()*4)::int,
       round((5 + random()*5)::numeric, 2)
FROM generate_series(1, 2000) g;

INSERT INTO courses (title, dept, credits, faculty_id)
SELECT 'Course ' || g,
       (ARRAY['CSE','ECE','MECH','CIVIL','MBA'])[1 + (g % 5)],
       2 + floor(random()*3)::int,
       1 + floor(random()*60)::int
FROM generate_series(1, 80) g;

INSERT INTO enrollments (student_id, course_id, semester, grade)
SELECT 1 + floor(random()*2000)::int,
       1 + floor(random()*80)::int,
       (ARRAY['2024-odd','2024-even','2025-odd'])[1 + floor(random()*3)::int],
       (ARRAY['A','B','C','D','F'])[1 + floor(random()*5)::int]
FROM generate_series(1, 12000);

INSERT INTO attendance (enrollment_id, class_date, present)
SELECT 1 + floor(random()*12000)::int,
       DATE '2025-01-01' + floor(random()*120)::int,
       random() < 0.8
FROM generate_series(1, 120000);

ANALYZE;
