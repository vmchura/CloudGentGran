# Parquet from S3 Example
```js
const data = FileAttachment("data/example-parquet.json").json();
display(Inputs.table(data))
Plot.plot({
  marks: [
    Plot.dot(data, {x: "year", y: "population_ge65", tip: true})
  ]
})
```