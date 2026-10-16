"""Public .gov document import with DNS pinning and bounded reads."""
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, unquote
from .documents import parse_document, section_text
from .config import settings


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'nav'}:
            self.hidden += 1
        if tag in {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'nav'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def fetch_government_document(url: str, redirects=0):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in {None, 443}
            or not host.endswith('.gov') or not host.isascii()):
        raise ValueError('Link imports require an HTTPS public .gov document URL. Upload other sources as files.')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('This URL does not resolve exclusively to public addresses.')
    # Connect to the validated address, preserving the hostname for TLS and HTTP.
    connection = http.client.HTTPSConnection(host, timeout=25)
    raw = socket.create_connection(addresses[0][4][:2], timeout=25)
    try:
        connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        connection.request('GET', path, headers={'User-Agent': 'Biddy/0.1 document importer', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status in {301, 302, 303, 307, 308}:
            if redirects >= 3:
                raise ValueError('Too many redirects. Upload the document instead.')
            return fetch_government_document(urljoin(url, response.getheader('Location', '')), redirects + 1)
        if response.status != 200:
            raise ValueError(f'The government source returned HTTP {response.status}. Download and upload the attachment instead.')
        data = response.read(settings().max_upload_bytes + 1)
        if len(data) > settings().max_upload_bytes:
            raise ValueError('Remote document exceeds 10 MB.')
        name = unquote(parsed.path.split('/')[-1]) or 'government-document.txt'
        ctype = response.getheader('Content-Type', '')
        if 'pdf' in ctype or data.startswith(b'%PDF'):
            return parse_document(data, 'document.pdf'), name
        if name.lower().endswith(('.docx', '.txt', '.md')):
            return parse_document(data, name), name
        if 'html' in ctype:
            parser = TextHTML()
            parser.feed(data.decode('utf-8', errors='replace'))
            text = ''.join(parser.parts).strip()
            if len(text) < 200 or len(text) > settings().max_document_chars:
                raise ValueError('No suitable solicitation text found. Upload its PDF attachment; dynamic SAM.gov pages are not documents.')
            return section_text(text), name
        return parse_document(data, 'document.txt'), name
    finally:
        connection.close()
        raw.close()
