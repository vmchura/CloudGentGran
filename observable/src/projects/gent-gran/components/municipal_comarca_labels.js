export function build_labels(municipal) {
    const municipal_name_label = Object.fromEntries(
        municipal.
            select("municipal_id", "municipal_name").
            dedupe("municipal_id", "municipal_name").
            objects().
            map(d => [d.municipal_id, d.municipal_name])
    );
    const comarca_name_label = Object.fromEntries(
        municipal.
            select("comarca_id", "comarca_name").
            dedupe("comarca_id", "comarca_name").
            objects().
            map(d => [d.comarca_id, d.comarca_name])
    );
    return { municipal_name_label, comarca_name_label };
}
