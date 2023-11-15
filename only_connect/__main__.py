import os.path
import ssl

from . import Servlet


ssl_ctx = None

if os.path.exists("cert.pem"):
    ssl_ctx = ssl.SSLContext()
    ssl_ctx.load_cert_chain("cert.pem")

Servlet().run(ssl_ctx)
