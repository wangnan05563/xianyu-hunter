import zipfile, io, re

pyc_path = r'src\xianyu_hunter\web\routes\__pycache__\auth_query.cpython-314.pyc'
with open(pyc_path, 'rb') as f:
    pyc = f.read()
print('pyc has isinstance:', b'isinstance' in pyc)
print('pyc has last_login:', b'last_login' in pyc)

pyz_path = r'build\xianyu-hunter\PYZ-00.pyz'
with open(pyz_path, 'rb') as f:
    pyz = f.read()
print('PYZ has isinstance:', b'isinstance' in pyz)
print('PYZ has last_login:', b'last_login' in pyz)

pkg_path = r'build\xianyu-hunter\xianyu-hunter.pkg'
with open(pkg_path, 'rb') as f:
    pkg = f.read()
pk_matches = list(re.finditer(b'PK\x03\x04', pkg))
print(f'PKG PK signatures: {len(pk_matches)}')
if pk_matches:
    try:
        z = zipfile.ZipFile(io.BytesIO(pkg[pk_matches[0].start():]))
        names = z.namelist()
        auth = [n for n in names if 'auth_query' in n]
        print(f'auth_query in PKG: {auth}')
        if auth:
            content = z.read(auth[0])
            has_is = b'isinstance' in content
            has_ll = b'last_login' in content
            print(f'PKG has isinstance: {has_is}')
            print(f'PKG has last_login: {has_ll}')
    except Exception as e:
        print(f'PKG error: {e}')
