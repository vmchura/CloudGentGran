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