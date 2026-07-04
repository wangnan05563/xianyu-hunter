import os
p = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\fetch_test.log"
print("dir exists:", os.path.exists(r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports"))
print("writable:", os.access(r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports", os.W_OK))
with open(p, "w", encoding="utf-8") as f:
    f.write("hello\n")
print("size:", os.path.getsize(p))
print("exists:", os.path.exists(p))
