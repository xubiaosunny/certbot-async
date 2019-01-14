# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import os
import json
import logging
import tornado.log
import random
import string
import functools
import hmac
import hashlib
import fcntl


def get_random_key():
    return ''.join(random.sample(string.ascii_letters + string.digits, 32))

config = {
    "domain": "xxx.xx",
    "certbot_path": "",
    "renew_period": 10,  # days
    "port": 8000,
    "access_key": get_random_key(),
}


class MyRequestHandler(tornado.web.RequestHandler):
    def _render_json(self, body):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(body))
        self.finish()

    def render_success(self, data):
        self._render_json({'status': 0, 'data': data})

    def render_error(self, msg):
        self._render_json({'status': 1, 'msg': msg})

    def render_unauthorized(self):
        self.render_error('Authorization fail')
        logging.warning('%s authorization fail' % self.request.remote_ip)


def access_auth(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if ('Authorization' in self.request.headers) and ('Date' in self.request.headers):
            h = hmac.new(config['access_key'].encode('utf-8'), self.request.headers['Date'].encode('utf-8'), digestmod='MD5')
            if self.request.headers['Authorization'] != h.hexdigest():
                self.render_unauthorized()
                return
            return func(self, *args, **kwargs)
        else:
            self.render_unauthorized()
            return
    return wrapper


class GetVersionHandler(MyRequestHandler):
    @access_auth
    def get(self):
        cert_file = '/etc/letsencrypt/live/%s/fullchain.pem' % config['domain']
        if not os.path.exists(cert_file):
            logging.error('certificate not exist')
            self.render_error('certificate not exist')
            return
        with open(cert_file, 'rb') as f:
            fmd5 = hashlib.md5(f.read())
        self.render_success({"version": fmd5.hexdigest()})


class RegistrationHandler(MyRequestHandler):
    @access_auth
    def get(self):
        self.render_success({})


class GetCertHandler(MyRequestHandler):
    @access_auth
    def get(self):
        ret = {}
        cert_path = os.path.join('/etc/letsencrypt/live/', config['domain'])
        if not os.path.exists(cert_path):
            self.render_error('certificate not exist')
            return

        for file_name in os.listdir(cert_path):
            if file_name not in ['README', 'cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem']:
                continue
            with open(os.path.join(cert_path, file_name), 'r') as f:
                ret[file_name] = f.read()

        self.render_success(ret)


def make_app():
    return tornado.web.Application([
        (r"/get_version", GetVersionHandler),
        (r"/registration", RegistrationHandler),
        (r"/get_cert", GetCertHandler),
    ])


def load_config():
    if os.path.exists('server_config.json'):
        with open('server_config.json', 'r') as f:
            user_config = json.load(f)
            for k in config.keys():
                if user_config.get(k, None):
                    config[k] = user_config[k]
    else:
        with open('server_config.json', 'w') as f:
            json.dump(config, f, indent=4)


def init_log():
    logger = logging.getLogger()
    # fm = tornado.log.LogFormatter(
    #     fmt='%(color)s[%(asctime)s %(filename)s:%(funcName)s:%(lineno)d %(le'
    #     'velname)s]%(end_color)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fm = tornado.log.LogFormatter(datefmt='%Y-%m-%d %H:%M:%S')
    tornado.log.enable_pretty_logging(logger=logger)
    logger.handlers[0].setFormatter(fm)


def certbot_renew():
    from OpenSSL import crypto
    import datetime
    cert_file = '/etc/letsencrypt/live/%s/fullchain.pem' % config['domain']
    if not os.path.exists(cert_file):
        logging.error('certificate not exist')
        return
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_file).read())
    not_after_str = cert.get_notAfter().decode('utf-8')
    not_after = datetime.datetime.strptime(not_after_str, '%Y%m%d%H%M%SZ')
    if (not_after - datetime.datetime.now()).days <= 20:
        cmd = "{} renew".format(config['certbot_path']) \
            if config['certbot_path'] else "certbot-auto renew"
        p = os.popen(cmd).read()
        logging.info(p)
    else:
        logging.info("notAfter is %s, renew skipped" % not_after_str)


if __name__ == "__main__":
    load_config()
    init_log()
    app = make_app()
    app.listen(config['port'])
    renew_period_ms = int(86400000 * float(config['renew_period']))
    tornado.ioloop.PeriodicCallback(certbot_renew, renew_period_ms).start()
    tornado.ioloop.IOLoop.current().start()
