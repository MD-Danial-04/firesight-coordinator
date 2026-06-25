alter table inference_jobs
  drop constraint if exists inference_jobs_message_type_check;

alter table inference_jobs
  add constraint inference_jobs_message_type_check
  check (message_type in ('stop_message', 'field_notes', 'interview'));

alter table inference_jobs
  add column if not exists interview_details_result jsonb;
