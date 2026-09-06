import ssl

from httpx import AsyncClient

custom_ssl_context = ssl.create_default_context()

http_client = AsyncClient(verify=custom_ssl_context)
