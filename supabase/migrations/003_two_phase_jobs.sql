alter table inference_jobs
  drop constraint if exists inference_jobs_status_check;

alter table inference_jobs
  add constraint inference_jobs_status_check
  check (status in ('pending', 'processing', 'transcribed', 'extract_pending', 'completed', 'failed'));

create or replace function claim_next_inference_job()
returns setof inference_jobs language sql as $$
  update inference_jobs
  set status = 'processing', claimed_at = now(), updated_at = now()
  where id = (
    select id from inference_jobs
    where status in ('pending', 'extract_pending')
    order by
      case
        when status = 'pending' then 0
        else 1
      end,
      created_at
    limit 1
    for update skip locked
  )
  returning *;
$$;
