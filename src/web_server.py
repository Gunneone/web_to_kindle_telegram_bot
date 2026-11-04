"""
Entrypoint for the web app (Eselsohr): `python src/web_server.py`.

One process on purpose: running deliveries, sign-in codes and rate limits are kept in memory.
Behind a reverse proxy, list the proxy's address in FORWARDED_ALLOW_IPS so client IPs are right.
"""

import logging
import os

import uvicorn

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s: %(message)s', level=logging.INFO)
    uvicorn.run('web.app:create_app', factory=True, host=os.getenv('WEB_HOST', '127.0.0.1'),
                port=int(os.getenv('WEB_PORT', '8000')), proxy_headers=True,
                forwarded_allow_ips=os.getenv('FORWARDED_ALLOW_IPS', '127.0.0.1'), workers=1)
