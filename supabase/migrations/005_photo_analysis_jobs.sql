alter table inference_jobs
  add column if not exists photo_path text,
  add column if not exists photo_context jsonb,
  add column if not exists photo_analysis_result jsonb;

insert into storage.buckets (id, name, public)
values ('inference-photos', 'inference-photos', false)
on conflict (id) do nothing;
