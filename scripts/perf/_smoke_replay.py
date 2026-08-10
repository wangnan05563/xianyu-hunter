import sys, json
sys.path.insert(0, ".")
from regression_replay import run

TOKEN = "PgEECYNIneqtk7fb-dyYvA4nzj3YTcjqPOVjZqAJATQ"
JMX = "D:/code/otherProjects/17_xianyu/test_results/jmeter/scripts/xianyu_load_test_reads.jmx"
meta = run(JMX, "http://127.0.0.1:8011", TOKEN, "D:/code/otherProjects/17_xianyu/test_results/jmeter/runs_smoke/reads_smoke.jsonl", duration_override=8)
print("SMOKE_META", json.dumps(meta, ensure_ascii=False))
