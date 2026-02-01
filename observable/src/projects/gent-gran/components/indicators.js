export async function calculateIndicators(db) {
  /* --------------------------------------------------
   * Years
   * -------------------------------------------------- */
  const all_years_tbl = await db.query(`
    SELECT DISTINCT year
    FROM social_services.comarca_population
    ORDER BY year
  `);
  const all_years = all_years_tbl.toArray().map(d => d.year);

  const { max_year: census_latest_year } =
    await db.queryRow(`
      SELECT MAX(year) AS max_year
      FROM social_services.comarca_population
    `);

  const { max_year: coverage_latest_year } =
    await db.queryRow(`
      SELECT MAX(year) AS max_year
      FROM social_services.comarca_coverage
    `);

  /* --------------------------------------------------
   * Latest year aggregates (Catalunya)
   * -------------------------------------------------- */
  const {
    total_population_latest_year,
    gent_gran_population_latest_year
  } = await db.queryRow(`
    SELECT
      SUM(population) AS total_population_latest_year,
      SUM(population_age_65_and_over) AS gent_gran_population_latest_year
    FROM social_services.comarca_population
    WHERE year = ${census_latest_year}
  `);

  const latest_indicator_average_catalunya =
    Math.round(
      gent_gran_population_latest_year * 1000 / total_population_latest_year
    ) / 10;

  const latest_indicator_average_catalunya_integer =
    Math.round(latest_indicator_average_catalunya);

  const range_colours_indicator =
    [...Array(8).keys()].map(i =>
      latest_indicator_average_catalunya_integer - 7 + i * 2
    );

  /* --------------------------------------------------
   * Reference year (closest to 2000)
   * -------------------------------------------------- */
  const reference_year =
    all_years.reduce((closest, year) =>
      Math.abs(year - 2000) < Math.abs(closest - 2000) ? year : closest
    );

  const {
    total_population_reference_year,
    gent_gran_population_reference_year
  } = await db.queryRow(`
    SELECT
      SUM(population) AS total_population_reference_year,
      SUM(population_age_65_and_over) AS gent_gran_population_reference_year
    FROM social_services.comarca_population
    WHERE year = ${reference_year}
  `);

  const reference_year_indicator_average_catalunya =
    Math.round(
      gent_gran_population_reference_year * 1000 / total_population_reference_year
    ) / 10;

  const sign_difference_reference =
    latest_indicator_average_catalunya_integer >
    reference_year_indicator_average_catalunya ? "+" : "";

  /* --------------------------------------------------
   * Social services (residences)
   * -------------------------------------------------- */
  const { number_places_residence } =
    await db.queryRow(`
      SELECT SUM(total_capacit) AS number_places_residence
      FROM social_services.social_services_empty_last_year
      WHERE service_type_id = 'RES-003'
    `);

  const catalunya_ratio_cobertura =
    Math.round(
      1000 * number_places_residence / gent_gran_population_latest_year
    ) / 10;

  const deficit_camas_residencia =
    Math.round(0.0411 * gent_gran_population_latest_year - number_places_residence);

  const deficit_superavit =
    deficit_camas_residencia > 0 ? "Dèficit" : "Superàvit";

  /* --------------------------------------------------
   * Coverage by comarca (latest year)
   * -------------------------------------------------- */
  const ratio_attention_latest_year_tbl =
    await db.query(`
      SELECT
        comarca_id,
        *,
        ROUND(0.0411 * population_age_65_and_over - total_capacit, 1) AS deficit_411
      FROM social_services.comarca_coverage
      WHERE year = ${census_latest_year}
    `);

  const ratio_attention_latest_year =
    Object.fromEntries(
      ratio_attention_latest_year_tbl.toArray()
        .map(d => [d.comarca_id, d])
    );

  /* --------------------------------------------------
   * Coverage by municipal (latest year)
   * -------------------------------------------------- */
  const ratio_attention_municipal_latest_year_tbl =
    await db.query(`
      SELECT *
      FROM social_services.municipal_coverage
      WHERE year = ${census_latest_year}
    `);

  const ratio_attention_municipal_latest_year =
    Object.fromEntries(
      ratio_attention_municipal_latest_year_tbl.toArray()
        .map(d => [d.municipal_id, d])
    );

  /* --------------------------------------------------
   * Population by comarca (latest & reference)
   * -------------------------------------------------- */
  const comarques_latest_population_tbl =
    await db.query(`
      SELECT
        comarca_id,
        population,
        population_age_65_and_over,
        ROUND(population_age_65_and_over * 100.0 / population, 1)
          AS elderly_indicator
      FROM social_services.comarca_population
      WHERE year = ${census_latest_year}
    `);

  const comarques_latest_population =
    Object.fromEntries(
      comarques_latest_population_tbl.toArray()
        .map(d => [d.comarca_id, d])
    );

  const comarques_reference_population_tbl =
    await db.query(`
      SELECT
        comarca_id,
        population,
        population_age_65_and_over,
        ROUND(population_age_65_and_over * 100.0 / population, 1)
          AS elderly_indicator
      FROM social_services.comarca_population
      WHERE year = ${reference_year}
    `);

  const comarques_reference_population =
    Object.fromEntries(
      comarques_reference_population_tbl.toArray()
        .map(d => [d.comarca_id, d])
    );

  /* --------------------------------------------------
   * Population by municipal (latest)
   * -------------------------------------------------- */
  const municipal_latest_population_tbl =
    await db.query(`
      SELECT
        municipal_id,
        population,
        population_age_65_and_over,
        ROUND(population_age_65_and_over * 100.0 / population, 1)
          AS elderly_indicator
      FROM social_services.population
      WHERE year = ${census_latest_year}
    `);

  const municipal_latest_population =
    Object.fromEntries(
      municipal_latest_population_tbl.toArray()
        .map(d => [d.municipal_id, d])
    );

  /* --------------------------------------------------
   * Return
   * -------------------------------------------------- */
  return {
    all_years,
    census_latest_year,
    reference_year,
    coverage_latest_year,
    latest_indicator_average_catalunya,
    latest_indicator_average_catalunya_integer,
    reference_year_indicator_average_catalunya,
    range_colours_indicator,
    sign_difference_reference,
    total_population_latest_year,
    gent_gran_population_latest_year,
    total_population_reference_year,
    gent_gran_population_reference_year,
    number_places_residence,
    catalunya_ratio_cobertura,
    deficit_camas_residencia,
    deficit_superavit,
    ratio_attention_latest_year,
    ratio_attention_municipal_latest_year,
    comarques_latest_population,
    comarques_reference_population,
    municipal_latest_population
  };
}

