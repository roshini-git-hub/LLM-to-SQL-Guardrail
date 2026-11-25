-- The same read-only login role, with grants that suit THIS database.
-- Students' contact details and faculty salaries are not granted.
GRANT CONNECT ON DATABASE college_db TO guardrail_ro;
GRANT USAGE ON SCHEMA public TO guardrail_ro;

GRANT SELECT ON courses, enrollments, attendance TO guardrail_ro;
GRANT SELECT (student_id, full_name, dept, admission_year, cgpa) ON students TO guardrail_ro;
GRANT SELECT (faculty_id, full_name, dept, designation) ON faculty TO guardrail_ro;
