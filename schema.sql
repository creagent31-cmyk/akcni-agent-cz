create table if not exists public.price_observations (
 id bigint generated always as identity primary key,
 retailer text not null,
 store text not null default 'online',
 sku text not null,
 product_name text not null,
 package text,
 price_czk numeric(12,2) not null check(price_czk >= 0),
 price_type text not null default 'regular' check(price_type in ('regular','promotion','loyalty')),
 source_url text,
 observed_on date not null,
 created_at timestamptz not null default now(),
 unique(retailer,store,sku,price_type,observed_on)
);
create index if not exists price_observations_lookup on public.price_observations(retailer,sku,observed_on desc);
alter table public.price_observations enable row level security;
grant select,insert,update on public.price_observations to service_role;
grant usage,select on sequence public.price_observations_id_seq to service_role;
