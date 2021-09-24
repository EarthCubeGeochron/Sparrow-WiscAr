ALTER TABLE analysis ADD COLUMN in_plateau boolean;
ALTER TABLE analysis ADD COLUMN data jsonb;

COMMIT;
