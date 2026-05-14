-- Personal Wellness Coach private storage buckets.
-- Jira: PPH-13

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values
  (
    'plan-files',
    'plan-files',
    false,
    26214400,
    array[
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv',
      'text/tab-separated-values',
      'text/plain',
      'text/markdown'
    ]
  ),
  (
    'checkin-evidence',
    'checkin-evidence',
    false,
    52428800,
    array[
      'image/jpeg',
      'image/png',
      'image/webp',
      'image/heic',
      'image/heif',
      'audio/mpeg',
      'audio/mp4',
      'audio/aac',
      'audio/wav',
      'audio/webm',
      'video/mp4',
      'video/quicktime',
      'application/pdf'
    ]
  ),
  (
    'avatars',
    'avatars',
    false,
    5242880,
    array[
      'image/jpeg',
      'image/png',
      'image/webp'
    ]
  )
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
