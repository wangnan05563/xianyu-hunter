"""Fetch API and parse"""
import urllib.request
import json
import os

# Read token from .env
token = ""
with open("d:/code/otherProjects/17_xianyu/.env", "r") as f:
    for line in f:
        if line.startswith("WEB_TOKEN="):
            token = line.split("=", 1)[1].strip()
            break

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/evaluations?limit=3",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

for i in data["items"]:
    p = i["payload"]
    print("---")
    print(f"title: {p.get('item_title')}")
    print(f"seller_nick: {p.get('seller_nick')!r}")
    print(f"region: {p.get('region')!r}")
    print(f"publish_time_text: {p.get('publish_time_text')!r}")
    print(f"seller_credit: {p.get('seller_credit')!r}")
    print(f"condition_label: {i.get('condition_label')!r}")
    print(f"condition_label_override: {p.get('condition_label_override')!r}")
