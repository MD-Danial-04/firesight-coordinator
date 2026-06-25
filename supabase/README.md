# Supabase setup

Run migrations in order in the Supabase SQL editor (or via `supabase db push` if using the CLI).

1. [`001_inference_jobs.sql`](./001_inference_jobs.sql) — base table
2. [`002_realtime_rls_claim.sql`](./002_realtime_rls_claim.sql) — claim RPC, Realtime, RLS, bucket
3. [`004_interview_analysis_jobs.sql`](./004_interview_analysis_jobs.sql) — interview analysis jobs
4. [`005_photo_analysis_jobs.sql`](./005_photo_analysis_jobs.sql) — photo analysis jobs + `inference-photos` bucket
5. [`006_interview_language_transcripts.sql`](./006_interview_language_transcripts.sql) — interview language + transcript columns
6. [`007_message_type_interview.sql`](./007_message_type_interview.sql) — allow `interview` message type + `interview_details_result` column

If the bucket insert in `002` fails, create **`inference-audio`** manually in Dashboard → Storage (private bucket).

If the bucket insert in `005` fails, create **`inference-photos`** manually in Dashboard → Storage (private bucket).

## API keys

The coordinator uses `supabase==2.31.0`, which supports both:

- **New keys:** `sb_secret_...` (coordinator) and `sb_publishable_...` (web Realtime)
- **Legacy JWT keys:** `eyJ...` service_role and anon

Use the **Project URL** only (no `/rest/v1` suffix):

```env
SUPABASE_URL=https://<project>.supabase.co
```

## Coordinator `.env`

```env
USE_FAKE_STORAGE=false
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<sb_secret_... or legacy service_role JWT>
SUPABASE_AUDIO_BUCKET=inference-audio
SUPABASE_PHOTO_BUCKET=inference-photos
WEB_API_KEY=<strong-key>
WORKER_API_KEY=<strong-key>
COORDINATOR_BASE_URL=http://localhost:8080
CORS_ORIGINS=http://localhost:5173
```

## Web app `.env`

```env
VITE_COORDINATOR_URL=http://localhost:8080
VITE_WEB_API_KEY=<same-as-WEB_API_KEY>
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<sb_publishable_... or legacy anon JWT>
```

## Verify

```bash
curl -X POST http://localhost:8080/v1/jobs \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -F "file=@sample.wav;type=audio/wav" \
  -F "message_type=stop_message" \
  -F "incident_type_name=Fire"
```

Check Supabase Table Editor for `status=pending` and Storage for `{job_id}/sample.wav`.
