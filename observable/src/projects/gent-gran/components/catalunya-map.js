import * as Plot from "@observablehq/plot";

export function set(input, value) {
  input.value = value;
  input.dispatchEvent(new Event("input", {bubbles: true}));
}

export function plot_catalunya_map_aged_65(width, comarques_boundaries, catalunya_indicator_or_variation,
  comarques_latest_population, comarques_reference_population,
  color_catalunya_map, plot_title) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: comarques_boundaries
    },
    color: color_catalunya_map,
    width: width,
    marks: [
      Plot.geo(comarques_boundaries, {
        fill: (d) => catalunya_indicator_or_variation == 1 ? comarques_latest_population[d.properties.comarca_id] :
          (comarques_latest_population[d.properties.comarca_id] - comarques_reference_population[d.properties.comarca_id]),
        title: d => d.properties.comarca_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}

export function plot_catalunya_map_coverage(width, comarques_boundaries,
  ratio_attention_latest_year, plot_title) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: comarques_boundaries
    },
    color: {
               type: "threshold",
               domain: [3, 4.11, 5],
               scheme: "blues",
               legend: true,
               pivot: 4.11,
               n: 10,
               unknown: "grey",
             },
    width: width,
    marks: [
      Plot.geo(comarques_boundaries, {
        fill: (d) => ratio_attention_latest_year[d.properties.comarca_id],
        title: d => d.properties.comarca_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}
export function plot_catalunya_map_coverage_municipal(width, single_comarque_boundaries,
  ratio_attention_latest_year, plot_title) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: single_comarque_boundaries
    },
    color: {
               type: "threshold",
               domain: [3, 4.11, 5],
               scheme: "blues",
               legend: true,
               pivot: 4.11,
               n: 10,
               unknown: "grey",
             },
    width: width,
    marks: [
      Plot.geo(single_comarque_boundaries, {
        fill: (d) => ratio_attention_latest_year[d.properties.municipal_id],
        title: d => d.properties.municipal_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
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