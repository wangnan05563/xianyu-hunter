# sync-sentence-transformers.py
# 修复 PyInstaller 收集的 sentence_transformers 缺少 __init__.py 等问题
import os, shutil
import sys

venv_st = sys.argv[1] if len(sys.argv) > 1 else r'D:\code\otherProjects\17_xianyu\.venv-build\Lib\site-packages\sentence_transformers'
dist_st = sys.argv[2] if len(sys.argv) > 2 else r'D:\code\otherProjects\17_xianyu\dist\xianyu-hunter\_internal\sentence_transformers'
venv_site = sys.argv[3] if len(sys.argv) > 3 else r'D:\code\otherProjects\17_xianyu\.venv-build\Lib\site-packages'
dist_internal = sys.argv[4] if len(sys.argv) > 4 else r'D:\code\otherProjects\17_xianyu\dist\xianyu-hunter\_internal'

def sync_missing(venv_dir, dist_dir):
    missing = 0
    for root, dirs, files in os.walk(venv_dir):
        rel = os.path.relpath(root, venv_dir)
        target = os.path.join(dist_dir, rel) if rel != '.' else dist_dir
        os.makedirs(target, exist_ok=True)
        for f in files:
            if '__pycache__' in f:
                continue
            src = os.path.join(root, f)
            dst = os.path.join(target, f)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                missing += 1
    return missing

if not os.path.exists(venv_st) or not os.path.exists(dist_st):
    print('[WARN] sentence_transformers dirs not found, skip')
    sys.exit(0)

result = sync_missing(venv_st, dist_st)
print(f'synced {result} missing files')

# Sync dist-info
for d in os.listdir(venv_site):
    if d.startswith('sentence_transformers-') and d.endswith('.dist-info'):
        src_info = os.path.join(venv_site, d)
        dst_info = os.path.join(dist_internal, d)
        if not os.path.exists(dst_info):
            shutil.copytree(src_info, dst_info)
            print(f'copied dist-info: {d}')
