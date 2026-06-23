alter table inference_jobs
  add column interview_language text check (interview_language in ('en', 'ms', 'ta', 'zh')),
  add column transcript_original text,
  add column transcript_english text;
