# Parquet from S3 Example
```js
const population_municipal_greater_65_table = FileAttachment("data/population_municipal_greater_65.parquet").parquet();
const comarques_boundaries = FileAttachment("data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("data/municipis-1000000.json").json();
```

```js
Plot.plot({
  marks: [
    Plot.dot(population_municipal_greater_65_table, {x: "year", y: "population_ge65", tip: true})
  ]
})
```