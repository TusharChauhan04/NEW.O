# Database Migrations

## The short version

**For any database — new or existing — run exactly one file:**

```
migrations/000_baseline_schema.sql
```

Paste it into the Supabase SQL Editor and run it. It is idempotent: safe to run
on a fresh project, and safe to re-run on a database that already has data.

---

## Why this exists

There used to be **three** scripts that each claimed to define the full schema:

| Script | Tables | `integrations` UNIQUE constraint |
|---|---|---|
| `scripts/init_db.sql` | 7 | *(no integrations table)* |
| `scripts/setup_complete.sql` | 12 | `(user_id, module, platform, label)` |
| `scripts/run_all_migrations.sql` | 10 | `(user_id, module, platform)` ← **different** |

Nothing recorded which had been applied to which database, so they drifted.
That constraint difference is not cosmetic: without `label` in the key, a tenant
is limited to **one integration per platform per module**, but the application
assigns a label per integration and expects to create several.

All three are now marked `DEPRECATED — DO NOT RUN`. They are kept for reference
rather than deleted, so any external notes pointing at them still resolve.

## What replaced them

`000_baseline_schema.sql` is the single source of truth. It:

- Creates every table the application actually uses (15 of them)
- Adds every column later phases introduced (`action_code`, `auto_executed`,
  `observe_only`, `override_enabled`, `sandbox`, `reward_value`, …)
- Applies RLS policies, including the `TO service_role` clause on
  `mistake_patterns` that was previously missing (without it, that policy
  applied to *every* role and effectively disabled RLS on the table)
- Repairs the `integrations` constraint drift, if present
- Seeds `reward_config`
- Creates a `schema_migrations` table so this can never silently drift again

### Safety contract

The file contains **no `DROP TABLE` and no `DELETE`**. Every create is
`IF NOT EXISTS`; every column add is `ADD COLUMN IF NOT EXISTS`. The single
constraint change only *widens* a uniqueness rule, which cannot conflict with
rows already in the table.

## Verifying it worked

```sql
-- Should list 000_baseline_schema plus the phases it subsumes
SELECT version, applied_at FROM schema_migrations ORDER BY version;

-- Should show ...platform_label_key (the 4-column form), not ...platform_key
SELECT conname FROM pg_constraint
WHERE conrelid = 'integrations'::regclass AND contype = 'u';

-- RLS check: the service-role policy must be scoped to {service_role},
-- NOT {public}. If it shows {public}, RLS on this table is not enforced.
SELECT policyname, roles, cmd FROM pg_policies
WHERE tablename = 'mistake_patterns';
```

## Adding a migration from here on

1. Create `migrations/<NNN>_<short_name>.sql` (e.g. `007_add_billing.sql`).
2. Make it idempotent — `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`.
3. End it with:
   ```sql
   INSERT INTO schema_migrations (version, note)
   VALUES ('007_add_billing', 'what this does')
   ON CONFLICT (version) DO NOTHING;
   ```
4. Do **not** edit `000_baseline_schema.sql` for schema changes — it represents
   the baseline, not the latest state.

## Optional / situational files

These are not part of the standard setup:

| File | Purpose |
|---|---|
| `migrations/bootstrap_admin.sql` | Promote one specific user to `role = 'admin'`. Edit the UUID inside before running. |
| `migrations/seed_test_data.sql` | Inserts sample events and pending decisions for local testing. **Do not run against production.** |
