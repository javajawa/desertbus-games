import os.path
import ssl

from . import Servlet

SSL_CTX = None

if os.path.exists("cert.pem"):
    SSL_CTX = ssl.SSLContext()
    SSL_CTX.load_cert_chain("cert.pem")

Servlet().run(SSL_CTX)
