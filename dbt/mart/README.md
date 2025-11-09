Welcome to your new dbt project!

### Using the starter project

Try running the following commands:
- dbt run --vars '{"downloaded_date": "20250920"}'
- dbt test

#### Read or show

```python
import duckdb

con = duckdb.connect("./local_data/catalunya_local.duckdb")

print("Row count in social_services_mart:",
con.execute("SELECT COUNT(*) FROM marts.social_services_mart;").fetchone())

# If there are rows, show a sample
    
try:
    sample = con.execute("SELECT * FROM marts.social_services_mart LIMIT 3;").fetchall()
    print("Sample from social_services_mart:", sample)
except Exception as e:
    print("Error querying social_services_mart:", e)

```

### Resources:
- Learn more about dbt [in the docs](https://docs.getdbt.com/docs/introduction)
- Check out [Discourse](https://discourse.getdbt.com/) for commonly asked questions and answers
- Join the [chat](https://community.getdbt.com/) on Slack for live discussions and support
- Find [dbt events](https://events.getdbt.com) near you
- Check out [the blog](https://blog.getdbt.com/) for the latest news on dbt's development and best practices
