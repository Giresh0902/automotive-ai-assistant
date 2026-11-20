-- Automotive AI Assistant: run in Supabase SQL editor
create extension if not exists vector;

create table if not exists vehicles (
  id uuid primary key default gen_random_uuid(),
  brand text not null,
  model text not null,
  segment text,
  created_at timestamptz default now(),
  unique (brand, model)
);

create table if not exists variants (
  id uuid primary key default gen_random_uuid(),
  vehicle_id uuid not null references vehicles(id) on delete cascade,
  name text not null,
  engine text, transmission text, fuel text, price text,
  key_specs jsonb default '{}'::jsonb,
  unique (vehicle_id, name)
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  vehicle_id uuid references vehicles(id) on delete set null,
  filename text not null,
  storage_path text not null,
  status text not null default 'processing',  -- processing | ready | failed
  error text,
  page_count int,
  uploaded_at timestamptz default now()
);

create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  vehicle_id uuid references vehicles(id) on delete set null,
  page_number int not null,
  content text not null,
  embedding vector(1536),
  metadata jsonb default '{}'::jsonb
);
create index if not exists chunks_embedding_idx on document_chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_vehicle_idx on document_chunks (vehicle_id);

create table if not exists chat_sessions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now()
);

create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null,
  sources jsonb default '[]'::jsonb,
  created_at timestamptz default now()
);
create index if not exists messages_session_idx on chat_messages (session_id, created_at);

create or replace function match_chunks(
  query_embedding vector(1536),
  match_count int default 8,
  filter_vehicle uuid default null
) returns table (
  id uuid, document_id uuid, vehicle_id uuid, page_number int,
  content text, filename text, storage_path text, model text, similarity float
) language sql stable as $$
  select c.id, c.document_id, c.vehicle_id, c.page_number, c.content,
         d.filename, d.storage_path, v.model,
         1 - (c.embedding <=> query_embedding) as similarity
  from document_chunks c
  join documents d on d.id = c.document_id
  left join vehicles v on v.id = c.vehicle_id
  where filter_vehicle is null or c.vehicle_id = filter_vehicle
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- Public bucket for brochure PDFs
insert into storage.buckets (id, name, public) values ('brochures','brochures',true)
on conflict (id) do nothing;
