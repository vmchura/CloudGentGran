export async function build_labels(db) {

  const municipal_tbl = await db.query(`
    SELECT DISTINCT
      municipal_id,
      municipal_name
    FROM social_services.municipal
  `);

  const municipal_name_label =
    Object.fromEntries(
      municipal_tbl.toArray()
        .map(d => [d.municipal_id, d.municipal_name])
    );

  const comarca_tbl = await db.query(`
    SELECT DISTINCT
      comarca_id,
      comarca_name
    FROM social_services.municipal
  `);

  const comarca_name_label =
    Object.fromEntries(
      comarca_tbl.toArray()
        .map(d => [d.comarca_id, d.comarca_name])
    );

  return { municipal_name_label, comarca_name_label };
}

