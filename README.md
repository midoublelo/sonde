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