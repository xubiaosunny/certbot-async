import requests
import datetime
import hmac
import os
import json
import sys
import hashlib
import fcntl
import getpass
import argparse


config = {
    "server_host": "http://127.0.0.1:8000",
    "access_key": '',
    "cert_dir": './letsencrypt',
    "after_script": "echo 'success'",

    "ssh_port": "22",
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
    return {
        'Authorization': h.hexdigest(),
        'Date': request_date,
        'Content-Type': 'application/json'
        }


def check_resp(data):
    if str(data['status']) == '0':
        return True
    else:
        print(data['msg'])
        sys.exit(0)


def request(url, method="GET", body=None):
    if method == "GET":
        res = requests.get(
            '%s%s' % (config['server_host'], url),
            headers=get_headers(), verify=False)
    elif method == "POST":
        res = requests.post(
            '%s%s' % (config['server_host'], url), headers=get_headers(),
            data=json.dumps(body), verify=False)
    else:
        raise ValueError('method "%s" not support' % method)
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
        p = os.popen(config['after_script']).read()
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


def register_service():
    abs_cert_dir = config['cert_dir'] if config['cert_dir'].startswith('/') \
        else os.path.join(
            os.path.abspath(os.path.dirname(__file__)), config['cert_dir'])
    body = {
        "user": getpass.getuser(),
        "ssh_port": config['ssh_port'],
        "cert_dir": abs_cert_dir,
        "after_script": config['after_script'],
    }
    data = request('/registration', method='POST', body=body)

    authorized_keys_path = os.path.join(
        os.path.expanduser('~'), '.ssh/authorized_keys')
    with open(authorized_keys_path, 'r') as f:
        authorized_keys = filter(
            lambda k: k.startswith('ssh-rsa'), f.read().split('\n'))
    if data['publickey'] not in authorized_keys:
        p = os.popen(
            'echo "%s" >> %s' % (data['publickey'], authorized_keys_path)
            ).read()
        print(p)


if __name__ == "__main__":
    load_config()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-rs", "--register", help="register service mode", action="store_true")
    args = parser.parse_args()
    if args.register:
        register_service()
    else:
        get_cert()
