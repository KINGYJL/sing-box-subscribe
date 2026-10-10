import tool,re
from urllib.parse import urlparse, parse_qs, unquote

def protect_userinfo_brackets(uri):
    """避免 urlparse 把密码中的方括号识别为 IPv6 地址。"""
    scheme, separator, remainder = uri.partition('://')
    if not separator:
        return uri

    match = re.search(r'[/?#]', remainder)
    end = match.start() if match else len(remainder)

    authority = remainder[:end]
    suffix = remainder[end:]

    userinfo, at, address = authority.rpartition('@')
    if not at:
        return uri

    userinfo = userinfo.replace('[', '%5B').replace(']', '%5D')

    return f'{scheme}{separator}{userinfo}@{address}{suffix}'

def parse(data):
    info = data[:]
    try:
        server_info = urlparse(protect_userinfo_brackets(info))
    except ValueError:
        return None
    if server_info.path:
      server_info = server_info._replace(netloc=server_info.netloc + server_info.path, path="")
    if '@' in server_info.netloc:
        _netloc = server_info.netloc.rsplit("@", 1)
    else:
        return None
    netquery = dict(
        (k, v if len(v) > 1 else v[0])
        for k, v in parse_qs(server_info.query).items()
    )
    node = {
        'tag': unquote(server_info.fragment) or tool.genName()+'_trojan',
        'type': 'trojan',
        'server': re.sub(r"\[|\]", "", _netloc[1].rsplit(":", 1)[0]),
        'server_port': int(_netloc[1].rsplit(":", 1)[1].split("/")[0]),
        'password': unquote(_netloc[0]),
        'tls': {
            'enabled': True,
            'insecure': False
        }
    }
    if netquery.get('allowInsecure') == '1':
        node['tls']['insecure'] = True
    if netquery.get('alpn'):
        node['tls']['alpn'] = netquery.get('alpn').strip('{}').split(',')
    if netquery.get('sni'):
        node['tls']['server_name'] = netquery.get('sni', '')
    if netquery.get('fp'):
        node['tls']['utls'] = {
            'enabled': True,
            'fingerprint': netquery.get('fp')
        }
    if netquery.get('type'):
        if netquery['type'] == 'h2':
            node['transport'] = {
                'type':'http',
                'host':netquery.get('host', node['server']),
                'path':netquery.get('path', '/')
            }
        if netquery['type'] == 'ws':
            path = netquery.get('path') or '/'
            match = re.search(r'\?ed=(\d+)$', path)
            node['transport'] = {
                    'type':'ws',
                    'path': path[:match.start()] if match else path,
                    'headers': {}
            }
            if match:
                node['transport'].update({
                    'early_data_header_name': 'Sec-WebSocket-Protocol',
                    'max_early_data': int(match.group(1))
                })
            if host := netquery.get('host'):
                node['transport']['headers']['Host'] = host
        elif netquery['type'] == 'grpc':
            node['transport'] = {
                'type':'grpc',
                'service_name':netquery.get('serviceName', '')
            }
    if netquery.get('protocol') in ['smux', 'yamux', 'h2mux']:
        node['multiplex'] = {
            'enabled': True,
            'protocol': netquery['protocol']
        }
        if netquery.get('max-streams'):
            node['multiplex']['max_streams'] = int(netquery['max-streams'])
        else:
            node['multiplex']['max_connections'] = int(netquery['max-connections'])
            node['multiplex']['min_streams'] = int(netquery['min-streams'])
        if netquery.get('padding') == 'True':
            node['multiplex']['padding'] = True
    return node
