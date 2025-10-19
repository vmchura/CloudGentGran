# Parquet from S3 Example
```js
import * as aq from "npm:arquero";
const { op } = aq;
```
```js
const social_services_zip_data = FileAttachment("data/social_services.zip").zip();
const comarques_boundaries = FileAttachment("data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("data/municipis-1000000.json").json();
```
```js
const comarca_population = aq.fromJSON(await social_services_zip_data.file("comarca_population.json").json());
const social_services_empty_last_year = aq.fromJSON(await social_services_zip_data.file("social_services_empty_last_year.json").json());
const municipal_coverage = aq.fromJSON(await social_services_zip_data.file("municipal_coverage.json").json());
const comarca_coverage = aq.fromJSON(await social_services_zip_data.file("comarca_coverage.json").json());
const municipal = aq.fromJSON(await social_services_zip_data.file("municipal.json").json());
```
```js
const nom_comarques = municipal.select('nom_comarca').dedupe('nom_comarca').array('nom_comarca');
```

```js
const all_years = comarca_population.dedupe('year').array('year');
const latest_year = Math.max(...all_years);
const population_latest_year = comarca_population
  .params({ latest_year })
  .filter((d, $) => d.year == $.latest_year);

const total_population_latest_year = population_latest_year
  .rollup({ total: d => aq.op.sum(d.population) })
  .get('total', 0);

const gent_gran_population_latest_year = population_latest_year
  .rollup({ total: d => aq.op.sum(d.population_ge65) })
  .get('total', 0);

const latest_indicator_average_catalunya = Math.round(gent_gran_population_latest_year * 1000 / total_population_latest_year) / 10.0;
const latest_indicator_average_catalunya_integer = Math.round(latest_indicator_average_catalunya);
const range_colours_indicator = [...Array(8).keys()].map(i => latest_indicator_average_catalunya_integer - 7 + i * 2);

const reference_year = all_years.reduce((closest, year) => 
  Math.abs(year - 2000) < Math.abs(closest - 2000) ? year : closest
);
const population_reference_year = comarca_population
  .params({ reference_year })
  .filter((d, $) => d.year == $.reference_year);

const total_population_reference_year = population_reference_year
  .rollup({ total: d => aq.op.sum(d.population) })
  .get('total', 0);

const gent_gran_population_reference_year = population_reference_year
  .rollup({ total: d => aq.op.sum(d.population_ge65) })
  .get('total', 0);

const reference_year_indicator_average_catalunya = Math.round(gent_gran_population_reference_year * 1000 / total_population_reference_year) / 10.0;

const sign_difference_reference = (latest_indicator_average_catalunya_integer > reference_year_indicator_average_catalunya)? "+" : "";
//const ratio_attention_latest_year = Object.fromEntries(ratio_attention_residence.filter(d => d.year == latest_year).map(row => [row.comarca, row.ratio]));
const number_places_residence = social_services_empty_last_year.filter(row => row.service_type_id == 'RES-003')
  .rollup({ total: d => aq.op.sum(d.total_capacit) })
  .get('total', 0);
```

```js
const catalunya_ratio_cobertura = Math.round(1000*number_places_residence / gent_gran_population_latest_year) / 10.0;
const deficit_camas_residencia = Math.round(0.0411*gent_gran_population_latest_year - number_places_residence);
const deficit_superavit = deficit_camas_residencia > 0 ? "Dèficit" : "Superàvit";
```

```js
const catalunya_indicator_or_variation_input = Inputs.radio(new Map([["Percentatge de la població de 65 anys i més", 1],
        [`Variació % població 65 anys i més entre els anys ${latest_year} i ${reference_year}`, 2],
        [`Taxa de cobertura de residència per a gent gran`, 3]]),
    {value: 1, label: "Indicador"});
const catalunya_indicator_or_variation = Generators.input(catalunya_indicator_or_variation_input);
```

```js
const all_title_map_by_indicator = ["Percentatge de la població de 65 anys i més",
    `Variació % població 65 anys i més entre els anys ${latest_year} i ${reference_year}`,
    "Porcentatge taxa de cobertura de residència per a gent gran"];
const all_messages_by_indicator = [`El següent mapa de Catalunya mostra cada comarca amb aquest indicador analitzat per a l'any ${latest_year}.
El valor central representa la mitjana de Catalunya, que és del ${latest_indicator_average_catalunya}% d'aquest indicador.
Com a referència addicional, la mediana global se situa en el 10%.`,
    `El següent mapa de Catalunya mostra la variació percentual de la població de 65 anys i més a cada comarca entre els anys ${latest_year} i ${reference_year}.`,
    "La taxa de cobertura de s'obté a partir del quocient entre el total de població de 65 anys i més i el total oferta de places. S'expressa en tant per cent"];
const title_map_by_indicator = all_title_map_by_indicator[catalunya_indicator_or_variation - 1];
const messages_by_indicator = all_messages_by_indicator[catalunya_indicator_or_variation - 1];
```

```js
const color_catalunya_map = catalunya_indicator_or_variation == 1 ? {
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
```

```js
function set(input, value) {
    input.value = value;
    input.dispatchEvent(new Event("input", {bubbles: true}));
}
```

```js
const render_interaction_comarca = (index, scales, values, dimensions, context, next) => {
    const dom_element = next(index, scales, values, dimensions, context);
    const all_paths = dom_element.querySelectorAll("path");
    for (let i = 0; i < all_paths.length; i++) {
        all_paths[i].addEventListener("click", () => {
            set(nom_comarca_input, nom_comarques[index[i]]);
        });
    }
    return dom_element;
}
```

```js
const ratio_attention_latest_year = Object.fromEntries(
  comarca_coverage.params({latest_year: latest_year})
    .filter(d => d.year === latest_year)
    .objects()
    .map(d => [d.comarca_id, d.coverage_ratio])
);

```
```js
const comarques_latest_population = Object.fromEntries(
  comarca_population.params({latest_year: latest_year})
    .filter((d, $) => d.year === $.latest_year)
    .select("comarca_id", "population_ge65", "population")
    .objects()
    .map(d => [
      d.comarca_id,
      Math.round((d.population_ge65 * 1000.0) / d.population) / 10.0
    ])
);
```

```js
const comarques_reference_population = Object.fromEntries(
  comarca_population.params({reference_year: reference_year})
    .filter((d, $) => d.year === $.reference_year)
    .select("comarca_id", "population_ge65", "population")
    .objects()
    .map(d => [
      d.comarca_id,
      Math.round((d.population_ge65 * 1000.0) / d.population) / 10.0
    ])
);
```
```js
const nom_comarca_input = Inputs.select(municipal.select('nom_comarca', 'codi_comarca').dedupe('nom_comarca', 'codi_comarca').orderby('nom_comarca'), {label: "Select one", format: x => x.nom_comarca, unique: true})
const nom_comarca = Generators.input(nom_comarca_input);

```
```js

const all_year_serveis_selected = social_services_empty_last_year.params({codi_comarca: nom_comarca.codi_comarca}).filter((d, $) => d.comarca_id == $.codi_comarca).select('year').array('year');
const max_year_serveis = Math.max(...all_year_serveis_selected);
const min_year_serveis = Math.min(...all_year_serveis_selected);
console.log(min_year_serveis);
console.log(max_year_serveis);
```

```js
const single_comarca_population_input = Inputs.radio(new Map([["Tendència de la població de 65 anys i més", true],
        ["Tendència de l'indicador de població de 65 anys i més", false]]),
    {value: true, label: null});
const single_comarca_population = Generators.input(single_comarca_population_input);
```
```js
const plot_legend_trend_population = (width) => {
    return Plot.legend({
        width: width,
        color: {
            domain: single_comarca_population ? ["population_over_65"] : ["indicator_elderly"],
            range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
            legend: false,
            columns: 1,
            rows: 2,
            label: null,
            tickFormat: d => d === "population_over_65" ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més"
        }
    });
}
```


```js
const plot_trend_population_groups_by_comarca = (width) => {
    return Plot.plot({
        marginLeft: 50,
        width: width,
        y: {
            grid: true,
            label: single_comarca_population ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més",
        },
        color: {
            domain: single_comarca_population ? ["population_over_65"] : ["indicator_elderly"],
            range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
            legend: false,
            columns: 1,
            rows: 2,
            label: null,
            tickFormat: d => d === "population_over_65" ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més"
        },
        x: {
            grid: true,
            tickFormat: d => d.toString(),
            interval: 1,
            label: null,
            domain: [min_year_serveis, max_year_serveis]
        },
        marks: [
            Plot.lineY(comarca_population.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis}).filter((row, $) => ((row.comarca_id == $.comarca_id) && (row.year >= $.min_year_serveis))),
                {x: "year",
                 y: (single_comarca_population ? "population_ge65" : "elderly_indicator"),
                 strokeWidth: 4}),
            Plot.ruleY([0])
        ]
    })
}
```


```js

const plot_catalunya_map_aged_65 = (width) => {
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
                render: render_interaction_comarca
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

};

```

```js
const service_tag_to_complete = new Map([["Servei de residència assistida", "Servei de residència assistida per a gent gran de caràcter temporal o permanent"],
    ["Servei de centre de dia", "Servei de centre de dia per a gent gran de caràcter temporal o permanent"],
    ["Servei de llar residència", "Servei de llar residència per a gent gran de caràcter temporal o permanent"],
    ["Servei de tutela", "Servei de tutela per a gent gran"],
    ["Servei d' habitatge tutelat", "Servei d' habitatge tutelat per a gent gran de caràcter temporal o permanent"]]);
const colour_by_service = new Map([["Servei de centre de dia per a gent gran de caràcter temporal o permanent", "#a160af"],
    ["Servei de residència assistida per a gent gran de caràcter temporal o permanent", "#ff9c38"],
    ["Servei de llar residència per a gent gran de caràcter temporal o permanent", "#f794b9"],
    ["Servei de tutela per a gent gran", "#61b0ff"],
    ["Servei d' habitatge tutelat per a gent gran de caràcter temporal o permanent", "#a87a54"]])
const all_services = Array.from(service_tag_to_complete.entries()).map(k => k[1]);
```

```js
const serveis_residence_ratio_input = Inputs.radio(new Map([["Tots els  serveis", true], ["Taxa de cobertura de residència per a gent gran", false]]),
    {value: true, label: null});
const serveis_residence_ratio = Generators.input(serveis_residence_ratio_input)
```
```js

const all_available_services = social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis}).filter((row, $) => (row.comarca_id === $.comarca_id) && (row.total_capacit > 0)).select('service_type_id').dedupe('service_type_id').array('service_type_id');

```


```js
const plot_comarca_by_serveis = (width) => {
    return Plot.plot({
        marginLeft: 50,
        width: width,
        y: {
            type: "linear",
            grid: true,
            label: "Places acumulativa del servei",
        },
        x: {
            label: null,
            grid: true,
            tickFormat: d => d.toString(),
            domain: [min_year_serveis, max_year_serveis],
            interval: 1
        },
        marks: [
            Plot.lineY(social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis}).filter((row, $) => (row.comarca_id === $.comarca_id)),
            Plot.mapY(
                "cumsum",
                Plot.groupX(
                { y: d => d3.sum(d, v => v.total_capacit) },
                { x: "year", curve: "step-after", z: "service_type_id", stroke: "service_type_id", tip: true}
                )
            ))
        ]
    })
};

const plot_comarca_by_cobertura = (width) => {
    return Plot.plot({
        marginLeft: 50,
        width: width,
        y: {
            type: "linear",
            grid: true,
            label: "Taxa de cobertura (%)",
        },
        color: {
            legend: false,
            columns: 1,
        },
        x: {
            label: null,
            grid: true,
            tickFormat: d => d.toString(),
            domain: [min_year_serveis, max_year_serveis]
        },
        marks: [
            Plot.lineY(comarca_coverage.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis}).filter((row, $) => (row.comarca_id === $.comarca_id)),
                {
                    x: "year", y: "coverage_ratio", stroke: "#ff9c38", strokeWidth: 2
                })
        ]
    })
};
```

```js
const plot_legend_trend_services = (width) => {
    return serveis_residence_ratio ? Plot.legend({
        width: width,
        color: {
            domain: all_available_services,
            range: all_available_services.map(row => colour_by_service.get(row)),
            legend: false,
            columns: 1,
            label: null,
        }
    }): Plot.legend({
        width: width,
        color: {
            domain: ["Taxa de cobertura de residència per a gent gran (%)"],
            range: ["#ff9c38"],
            legend: false,
            columns: 1,
            label: null,
        }
    });
}
```


<div class="grid grid-cols-3">
    <div class="card grid-colspan-2">
        <h2>${title_map_by_indicator}</h2>
${messages_by_indicator}
<br/>
<br/>
${catalunya_indicator_or_variation_input}
<br/>
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_catalunya_map_aged_65(width))}
        </figure>
    </div>
    <div class="grid-colspan-1">
        <h2>Catalunya ${latest_year}</h2>
        <div class="card">
            <h3 class="big-number-header">Població de 65 anys i més</h3>
            <span class="big grid-colspan-4">${Number(gent_gran_population_latest_year).toLocaleString('ca-ES')}</span>
        </div>  
        <div class="card">
            <h3 class="big-number-header">Percentatge de la població de 65 anys i més</h3>
            <span class="big grid-colspan-4">${Number(latest_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
            <h3 class="big-number-header">${`Variació % gent gran respecte a l'any ${reference_year}`}</h3>
            <span class="big grid-colspan-4">${sign_difference_reference}${Number(latest_indicator_average_catalunya - reference_year_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
            <h3 class="big-number-header">Places de residència per a gent gran</h3>
            <span class="big grid-colspan-4">${Number(number_places_residence).toLocaleString('ca-ES')}</span>
        </div>
        <div class="card">
            <h3 class="big-number-header">Taxa de cobertura de residència per a gent gran</h3>
            <span class="big grid-colspan-4">${Number(catalunya_ratio_cobertura).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
            <h3 class="big-number-header">${deficit_superavit} de places per cobertura del 4,11%</h3>
            <span class="big grid-colspan-4">${Number(deficit_camas_residencia).toLocaleString('ca-ES')}</span>
        </div>
    </div>
</div>

<div class="grid grid-cols-3">
    <h2 class="grid-colspan-2"> Tendència de la població de 65 anys i més i els serveis d'assistència per comarca. </h2>
    <div class="grid-colspan-1" style="align-self: center;">${nom_comarca_input}</div>
</div>

<div class="grid grid-cols-3">
    <div class="grid-colspan-1">
        <h2>Tendència de la població de 65 anys i més</h2>
            ${single_comarca_population_input}
            ${resize((width) => plot_legend_trend_population(width))}
    </div>
    <div class="grid-colspan-1">
        <h2>Serveis d'assistència</h2>
            ${serveis_residence_ratio_input}
            ${resize((width) => plot_legend_trend_services(width))}
    </div>
    <div class="grid-colspan-1">
        <h2>Qualificaciò de los servei</h2>
            ${serveis_input}
            ${resize((width) => plot_legend_trend_iniciative(width))} 
    </div>
</div>

<div class="grid grid-cols-3">
    <div class="card grid-colspan-1">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_trend_population_groups_by_comarca(width))}
        </figure>
    </div>
    <div class="card grid-colspan-1">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => serveis_residence_ratio ? plot_comarca_by_serveis(width) : plot_comarca_by_cobertura(width))}
        </figure>
    </div>
    <div class="card grid-colspan-1">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_services_comarca_by_iniciatives(width))}
        </figure>
    </div>

</div>