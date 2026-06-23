-- Message type constraint
alter table inference_jobs
  add constraint inference_jobs_message_type_check
  check (message_type in ('stop_message', 'field_notes'));

-- Auto-update updated_at on row changes
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger inference_jobs_updated_at
  before update on inference_jobs
  for each row execute function set_updated_at();

-- Atomic job claim for worker polling (FOR UPDATE SKIP LOCKED)
create or replace function claim_next_inference_job()
returns setof inference_jobs language sql as $$
  update inference_jobs
  set status = 'processing', claimed_at = now(), updated_at = now()
  where id = (
    select id from inference_jobs
    where status = 'pending'
    order by created_at
    limit 1
    for update skip locked
  )
  returning *;
$$;

-- Enable Realtime on inference_jobs
alter publication supabase_realtime add table inference_jobs;

-- RLS: anon can read jobs (for web Realtime); coordinator uses service role for writes
alter table inference_jobs enable row level security;

create policy "anon_read_jobs" on inference_jobs
  for select to anon using (true);

-- Storage bucket (run in Dashboard if this fails — bucket creation via SQL varies by Supabase version)
insert into storage.buckets (id, name, public)
values ('inference-audio', 'inference-audio', false)
on conflict (id) do nothing;
