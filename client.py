import requests
import datetime
import hmac
import os
import json


config = {
    "host": "127.0.0.1:8000",
    "access_key": '',
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
    request_date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    h = hmac.new(config['access_key'].encode('utf-8'), request_date.encode('utf-8'), digestmod='MD5')
    return {'Authorization': h.hexdigest(), 'Date': request_date}


if __name__ == "__main__":
    load_config()
    res = requests.get('http://127.0.0.1:8000/get_version', headers=get_headers())
