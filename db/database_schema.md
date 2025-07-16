# Database Schema

## Enum Types

- **plugin_type**: `'RING'`

---

## Table: vendors
| Column         | Type                | Constraints                |
|---------------|---------------------|----------------------------|
| vendor_id      | serial4             | PK, not null               |
| name           | text                | not null                   |
| token          | bytea               |                            |
| token_expires  | timestamptz         |                            |
| auth_data      | jsonb               | not null, default `{}`     |
| created_at     | timestamptz         | not null, default now      |
| updated_at     | timestamptz         | not null, default now      |
| username       | text                | not null                   |
| password_enc   | text                | not null                   |
| plugin_type    | plugin_type         |                            |

---

## Table: motion_events
| Column                        | Type           | Constraints                |
|-------------------------------|----------------|----------------------------|
| id                            | serial4        | PK, not null               |
| camera_name                   | text           | not null                   |
| motion_detected               | timestamptz    | not null                   |
| uploaded_to_s3                | timestamptz    | not null                   |
| facial_recognition_processed  | timestamptz    | not null                   |
| s3_url                        | text           |                            |
| created_at                    | timestamptz    | not null, default now      |
| updated_at                    | timestamptz    | not null, default now      |
| event_metadata                | jsonb          | not null, default `{}`     |

---

## Table: visitor_logs
| Column            | Type        | Constraints                |
|-------------------|------------|----------------------------|
| visitor_log_id    | serial4     | PK, not null               |
| camera_name       | text        | not null                   |
| persons_name      | text        | not null                   |
| confidence_score  | float8      | not null                   |
| visited_at        | timestamptz | not null                   |
| created_at        | timestamptz | not null, default now      |

---

## Indexes
- `motion_events_pkey` (id, motion_events)
- `idx_motion_events_camera_time` (camera_name, motion_detected, motion_events)
- `visitor_log_pkey` (visitor_log_id, visitor_logs)
- `idx_visitor_logs_visited_at` (visited_at, visitor_logs)

---

## Sequences
- motion_events_event_id_seq
- vendors_vendor_id_seq
- visitor_log_visitor_id_seq

---

## Roles & Permissions
- Role: `app_user`
    - USAGE, CREATE on schema public
    - SELECT, INSERT, UPDATE, DELETE on all tables in schema public
    - USAGE, SELECT on all sequences in schema public