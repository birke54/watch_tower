-- Create the app_user role if it does not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN;
    END IF;
END
$$;

-- Grant permissions to app_user
GRANT USAGE ON SCHEMA public TO app_user;
GRANT CREATE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Create enum types if they do not exist
DO $$ BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'plugin_type') THEN
		CREATE TYPE public.plugin_type AS ENUM ('RING');
	END IF;
END $$;

-- public.motion_events definition
CREATE TABLE IF NOT EXISTS public.motion_events (
	id serial4 PRIMARY KEY,
	camera_name text NOT NULL,
	motion_detected timestamptz NOT NULL,
	uploaded_to_s3 timestamptz NOT NULL,
	facial_recognition_processed timestamptz NOT NULL,
	s3_url text,
	created_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
	event_metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);

-------------------------------------------------------------------------------------------

-- public.vendors definition
CREATE TABLE IF NOT EXISTS public.vendors (
	vendor_id serial4 PRIMARY KEY,
	name text NOT NULL,
	token bytea,
	token_expires timestamptz,
	auth_data jsonb DEFAULT '{}'::jsonb NOT NULL,
	created_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
	username text NOT NULL,
	password_enc text NOT NULL,
	plugin_type public.plugin_type
);

-------------------------------------------------------------------------------------------

-- public.visitor_logs definition
CREATE TABLE IF NOT EXISTS public.visitor_logs (
	visitor_log_id serial4 PRIMARY KEY,
	camera_name text NOT NULL,
	persons_name text NOT NULL,
	confidence_score float8 NOT NULL,
	visited_at timestamptz NOT NULL,
	created_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_visitor_logs_visited_at ON public.visitor_logs(visited_at);
CREATE INDEX IF NOT EXISTS idx_motion_events_camera_time ON public.motion_events(camera_name, motion_detected);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
	NEW.updated_at = CURRENT_TIMESTAMP;
	RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updating updated_at
CREATE TRIGGER update_vendors_updated_at
	BEFORE UPDATE ON public.vendors
	FOR EACH ROW
	EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_motion_events_updated_at
	BEFORE UPDATE ON public.motion_events
	FOR EACH ROW
	EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visitor_logs_updated_at
	BEFORE UPDATE ON public.visitor_logs
	FOR EACH ROW
	EXECUTE FUNCTION update_updated_at_column();