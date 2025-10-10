# Parquet from S3 Example
```js
const population = FileAttachment("data/population_municipal_greater_65.parquet").parquet();
const social_services_by_municipal = FileAttachment("data/social_services_by_service_municipal.parquet").parquet();
const comarques_boundaries = FileAttachment("data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("data/municipis-1000000.json").json();
```

```js
const years = population.getChild('year').toArray();
const latest_year = years.reduce((a, b) => (a > b ? a : b));

```

${latest_year}