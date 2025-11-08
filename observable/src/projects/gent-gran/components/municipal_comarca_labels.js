export function build_labels(municipal) {
    const municipal_name_label = Object.fromEntries(
        municipal.
            select("codi", "nom").
            dedupe("codi", "nom").
            objects().
            map(d => [d.codi, d.nom])
    );
    const comarca_name_label = Object.fromEntries(
        municipal.
            select("codi_comarca", "nom_comarca").
            dedupe("codi_comarca", "nom_comarca").
            objects().
            map(d => [d.codi_comarca, d.nom_comarca])
    );
    return { municipal_name_label, comarca_name_label };
}