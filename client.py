import requests
import datetime
import hmac
import os
import json
import sys
import hashlib
import fcntl


config = {
    "host": "127.0.0.1:8000",
    "access_key": '',
    "cert_dir": './letsencrypt',
    "script": "echo 'success'"
}


def load_config():
    if os.path.exists('client_config.json'):
        with open('client_config.json', 'r') as f:
            user_config = json.load(f)
            for k in config.keys():
                if user_config.get(k, None):
                    config[k] = user_config[k]
    else:
        with open('client_config.json', 'w') as f:
            json.dump(config, f, indent=4)


def get_headers():
    request_date = datetime.datetime.utcnow().strftime(
        '%a, %d %b %Y %H:%M:%S GMT')
    h = hmac.new(
        config['access_key'].encode('utf-8'),
        request_date.encode('utf-8'),
        digestmod='MD5')
    return {'Authorization': h.hexdigest(), 'Date': request_date}


def check_resp(data):
    if str(data['status']) == '0':
        return True
    else:
        print(data['msg'])
        sys.exit(0)


def request(url):
    res = requests.get('%s%s' % (config['host'], url), headers=get_headers())
    data = res.json()
    if str(data['status']) != '0':
        print(data['msg'])
        sys.exit(0)
    return data['data']


def get_cert():
    def _get_cert():
        certs = request('/get_cert')
        for name, content in certs.items():
            with open(os.path.join(config['cert_dir'], name), 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(content)
        p = os.popen(config['script']).read()
        print(p)    

    if not os.path.exists(config['cert_dir']):
        os.makedirs(config['cert_dir'])

    data = request('/get_version')
    cert_file = os.path.join(config['cert_dir'], 'fullchain.pem')
    if os.path.exists(cert_file):
        with open(cert_file, 'rb') as f:
            fmd5 = hashlib.md5(f.read())
        if fmd5.hexdigest() != data['version']:
            _get_cert()
    else:
        _get_cert()


if __name__ == "__main__":
    load_config()
    get_cert()
