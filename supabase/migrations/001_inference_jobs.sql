create table inference_jobs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  status text not null check (status in ('pending', 'processing', 'completed', 'failed')),
  audio_path text not null,
  message_type text not null default 'stop_message',
  incident_type_name text,
  transcript text,
  result jsonb,
  error text,
  claimed_at timestamptz,
  completed_at timestamptz
);

create index inference_jobs_status_created_idx on inference_jobs (status, created_at);

-- RLS policies should be added when wiring real Supabase access.
-- The coordinator uses the service role key and enforces auth at the API layer.
