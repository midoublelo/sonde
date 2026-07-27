# Sonde

data-driven platform for the london underground

```bash
pip install -r requirements.txt
python -m scripts.init_db
python -m scripts.build_graph
python -m scripts.run_ingestion   # do one poll to confirm it works
```

```bash
python -m scripts.find_route "Oxford Circus" "King's Cross"
python -m scripts.find_route "Oxford Circus" "King's Cross" --live
```

```bash
streamlit run app.py
```

```bash
python -m scripts.analyze_network
```

## Spark analysis (optional)

The "Spark" tab reads pre-computed results from a separate
Scala/Apache Spark batch pipeline (`sonde-spark/`), rather than the
Python/SQLite path used elsewhere in the app.

To regenerate:
```
cd sonde-spark
sbt run
# pick WriteAnalysisOutputs if prompted for a main class
```