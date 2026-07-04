import urllib.request
import urllib.error
try:
    r = urllib.request.urlopen('http://localhost:9000/api/system/status', timeout=10)
    print('STATUS:', r.status)
    print('BODY:', r.read().decode()[:300])
except Exception as e:
    print('ERROR:', type(e).__name__, str(e)[:300])
