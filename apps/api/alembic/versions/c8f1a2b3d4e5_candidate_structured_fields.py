"""candidate profile structured fields

work_mode text -> text[]; languages text[] -> jsonb; education text -> jsonb.
experience stays jsonb but its objects change shape (period -> startYear/endYear).
Only demo-seeded data exists; conversions are best-effort and reversible.

Revision ID: c8f1a2b3d4e5
Revises: 5f2f2fb3a1af
"""

from alembic import op

revision = "c8f1a2b3d4e5"
down_revision = "5f2f2fb3a1af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # work_mode: text -> text[] (wrap a non-empty scalar into a one-element array)
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN work_mode TYPE text[] "
        "USING (CASE WHEN work_mode IS NULL OR work_mode = '' "
        "THEN '{}'::text[] ELSE ARRAY[work_mode] END)"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode SET DEFAULT '{}'")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode SET NOT NULL")

    # languages: text[] -> jsonb [{language, level:""}]
    # (Postgres rejects a bare subquery in an ALTER COLUMN TYPE ... USING transform
    # expression, so the per-element aggregation is wrapped in a throwaway pg_temp function.)
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages DROP DEFAULT")
    op.execute(
        "CREATE FUNCTION pg_temp.candidate_languages_to_jsonb(langs text[]) "
        "RETURNS jsonb AS $$ SELECT coalesce(jsonb_agg(jsonb_build_object("
        "'language', e, 'level', '')), '[]'::jsonb) FROM unnest(langs) AS e $$ "
        "LANGUAGE sql"
    )
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN languages TYPE jsonb "
        "USING pg_temp.candidate_languages_to_jsonb(languages)"
    )
    op.execute("DROP FUNCTION pg_temp.candidate_languages_to_jsonb(text[])")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages SET DEFAULT '[]'::jsonb")

    # education: text -> jsonb [{degree, field, institution, year}]
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN education TYPE jsonb "
        "USING (CASE WHEN education IS NULL OR education = '' THEN '[]'::jsonb "
        "ELSE jsonb_build_array(jsonb_build_object("
        "'degree','', 'field', education, 'institution','', 'year', NULL)) END)"
    )
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education SET NOT NULL")

    # experience: rewrite {role, org, period} -> {role, org, start_year, end_year}
    op.execute(
        r"""
        UPDATE candidate_profiles SET experience = coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                'role', e->>'role',
                'org', e->>'org',
                'start_year', NULLIF(substring(e->>'period' from '(\d{4})'), '')::int,
                'end_year', CASE
                    WHEN e->>'period' ~* 'now|present' THEN NULL
                    ELSE NULLIF(substring(e->>'period' from '(\d{4})\D*$'), '')::int
                END))
            FROM jsonb_array_elements(experience) AS e)
        , '[]'::jsonb)
        WHERE jsonb_typeof(experience) = 'array'
          AND experience @> '[{"period": null}]' IS NOT TRUE
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(experience) AS e WHERE e ? 'period')
        """
    )


def downgrade() -> None:
    # experience: {start_year, end_year} -> {period}
    op.execute(
        """
        UPDATE candidate_profiles SET experience = coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                'role', e->>'role',
                'org', e->>'org',
                'period', concat_ws(' — ', e->>'start_year',
                    coalesce(e->>'end_year', 'now'))))
            FROM jsonb_array_elements(experience) AS e)
        , '[]'::jsonb)
        WHERE jsonb_typeof(experience) = 'array'
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(experience) AS e WHERE e ? 'start_year')
        """
    )

    # education: jsonb -> text (first row's field)
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education DROP DEFAULT")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN education DROP NOT NULL")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN education TYPE text "
        "USING (CASE WHEN jsonb_array_length(education) = 0 THEN NULL "
        "ELSE education->0->>'field' END)"
    )

    # languages: jsonb -> text[] (same subquery-in-USING workaround as upgrade())
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages DROP DEFAULT")
    op.execute(
        "CREATE FUNCTION pg_temp.candidate_languages_to_textarray(langs jsonb) "
        "RETURNS text[] AS $$ SELECT coalesce(array_agg(e->>'language'), "
        "'{}'::text[]) FROM jsonb_array_elements(langs) AS e $$ LANGUAGE sql"
    )
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN languages TYPE text[] "
        "USING pg_temp.candidate_languages_to_textarray(languages)"
    )
    op.execute("DROP FUNCTION pg_temp.candidate_languages_to_textarray(jsonb)")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN languages SET DEFAULT '{}'")

    # work_mode: text[] -> text (join)
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode DROP DEFAULT")
    op.execute("ALTER TABLE candidate_profiles ALTER COLUMN work_mode DROP NOT NULL")
    op.execute(
        "ALTER TABLE candidate_profiles ALTER COLUMN work_mode TYPE text "
        "USING (CASE WHEN cardinality(work_mode) = 0 THEN NULL "
        "ELSE array_to_string(work_mode, ', ') END)"
    )
