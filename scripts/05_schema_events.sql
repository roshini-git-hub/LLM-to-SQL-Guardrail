-- Tell the guardrail when the schema or permissions change.
-- An event trigger fires after every DDL command (CREATE/ALTER/DROP, GRANT/REVOKE,
-- COMMENT, CREATE POLICY, ...) and sends NOTIFY on channel 'schema_changed'.
-- The guardrail LISTENs on that channel and reloads its schema snapshot.
-- Event triggers must be created by a superuser:
--   psql -d guardrail_db -f scripts/05_schema_events.sql

CREATE OR REPLACE FUNCTION notify_schema_changed() RETURNS event_trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('schema_changed', tg_tag);
END;
$$;

DROP EVENT TRIGGER IF EXISTS guardrail_schema_changed;
CREATE EVENT TRIGGER guardrail_schema_changed
    ON ddl_command_end
    EXECUTE FUNCTION notify_schema_changed();
