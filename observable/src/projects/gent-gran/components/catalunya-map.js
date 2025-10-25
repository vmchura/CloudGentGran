export function set(input, value) {
  input.value = value;
  input.dispatchEvent(new Event("input", {bubbles: true}));
}

export function render_interaction_comarca(nom_comarques, nom_comarca_input) {
  return (index, scales, values, dimensions, context, next) => {
    const dom_element = next(index, scales, values, dimensions, context);
    const all_paths = dom_element.querySelectorAll("path");
    for (let i = 0; i < all_paths.length; i++) {
      all_paths[i].addEventListener("click", () => {
        set(nom_comarca_input, nom_comarques[index[i]]);
      });
    }
    return dom_element;
  };
}

export function plot_catalunya_map_aged_65(width, comarques_boundaries, catalunya_indicator_or_variation,
  comarques_latest_population, comarques_reference_population, ratio_attention_latest_year,
  color_catalunya_map, nom_comarques, nom_comarca_input) {

  let plot = Plot.plot({
    projection: {
      type: "conic-conformal",
      domain: comarques_boundaries
    },
    color: color_catalunya_map,
    width: width,
    marks: [
      Plot.geo(comarques_boundaries, {
        fill: (d) => catalunya_indicator_or_variation == 1 ? comarques_latest_population[d.properties.comarca_id] :
          (catalunya_indicator_or_variation == 2 ? comarques_latest_population[d.properties.comarca_id] - comarques_reference_population[d.properties.comarca_id] :
            ratio_attention_latest_year[d.properties.comarca_id]),
        title: d => d.properties.comarca_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true,
        render: render_interaction_comarca(nom_comarques, nom_comarca_input)
      })
    ]
  });

  d3.select(plot)
    .selectAll("path")
    .on("mouseover", function () {
      d3.select(this).attr("stroke-width", 4.0);
    })
    .on("mouseout", function () {
      d3.select(this).attr("stroke-width", 1.0);
    });

  d3.select(plot)
    .on("pointerenter", function () {
      d3.select(plot).selectAll("path").attr("stroke-width", 1.0);
    })
    .on("pointerleave", function () {
      d3.select(plot).selectAll("path").attr("stroke-width", 1.0);
    });

  return plot;
}

export function getColorCatalunyaMap(catalunya_indicator_or_variation, latest_indicator_average_catalunya_integer, range_colours_indicator) {
  return catalunya_indicator_or_variation == 1 ? {
    type: "threshold",
    scheme: "buylrd",
    legend: true,
    pivot: latest_indicator_average_catalunya_integer,
    n: 10,
    unknown: "grey",
    domain: range_colours_indicator,
  } : (catalunya_indicator_or_variation == 2 ? {
    type: "diverging",
    scheme: "buylrd",
    legend: true,
    pivot: 0,
    n: 10,
    unknown: "grey",
  } : {
    type: "threshold",
    domain: [2, 4, 6],
    scheme: "blues",
    legend: true,
    pivot: 4.11,
    n: 10,
    unknown: "grey",
  });
}