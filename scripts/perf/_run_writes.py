import sys
sys.path.insert(0, ".")
from regression_replay import run

TOKEN = "PgEECYNIneqtk7fb-dyYvA4nzj3YTcjqPOVjZqAJATQ"
JMX = "D:/code/otherProjects/17_xianyu/test_results/jmeter/scripts/xianyu_load_test_writes.jmx"
OUT = "D:/code/otherProjects/17_xianyu/test_results/jmeter/runs_p0p1/writes.jsonl"
run(JMX, "http://127.0.0.1:8011", TOKEN, OUT)
