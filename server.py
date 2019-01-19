# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.httpserver
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
import sys


def get_random_key():
    return ''.join(random.sample(string.ascii_letters + string.digits, 32))

config = {
    "domain": "xxx.xx",
    "certbot_path": "",
    "renew_period": 10,  # days
    "port": 8000,
    "access_key": get_random_key(),

    "smtp_server": "",
    "smtp_port": "",
    "smtp_ssl": True,
    "smtp_email": "",
    "smtp_password": "",
    "notify_receiver": "",
}

CERT_FILE_NAME_LIST = ['README', 'cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem']
BASE_PATH = os.path.abspath(os.path.dirname(__file__))


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

    def render_forbidden(self):
        self.render_error('Forbidden')
        logging.warning('%s Forbidden' % self.request.remote_ip)

    def get_json(self):
        body = self.request.body
        if isinstance(self.request.body, bytes):
            body = body.decode('utf-8')
        return json.loads(body)


def access_auth(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if os.path.exists('whitelist.txt'):
            with open('whitelist.txt', 'r') as f:
                whitelist = f.read().split('\n')
            if self.request.remote_ip not in whitelist:
                self.render_forbidden()
                return

        if ('Authorization' in self.request.headers) and \
           ('Date' in self.request.headers):
            h = hmac.new(
                config['access_key'].encode('utf-8'),
                self.request.headers['Date'].encode('utf-8'), digestmod='MD5')
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
    def post(self):
        import sqlite3
        # update db
        data = self.get_json()
        conn = sqlite3.connect('server.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM registration where ip=?;", (self.request.remote_ip, ))
        if cursor.fetchall():
            cursor.execute(
                "update registration set user = ?, ssh_port = ?, cert_dir = ?, after_script = ?, last_timestamp=strftime('%s', 'now') where ip=?;", 
                (data['user'], data['ssh_port'], data['cert_dir'], data['after_script'], self.request.remote_ip))
        else:
            cursor.execute(
                'insert into registration (ip, user, ssh_port, cert_dir, after_script) values (?, ?, ?, ?, ?);', 
                (self.request.remote_ip, data['user'], data['ssh_port'], data['cert_dir'], data['after_script']))
        cursor.close()
        conn.commit()
        conn.close()
        # set .ssh/known_hosts
        known_hosts_path = os.path.join(os.path.expanduser('~'), '.ssh/known_hosts')
        client_publickey = os.popen("ssh-keyscan -t rsa %s" % self.request.remote_ip).read()
        with open(known_hosts_path) as f:
            for line in f:
                line_s = line.replace('\n', '')
                if not line_s.startswith('#') and line_s.split(' ', 1)[0] == self.request.remote_ip:
                    logging.info('%s ssh publickey already exist!' % self.request.remote_ip)
                    key_l = list(filter(lambda s: s.startswith(self.request.remote_ip), client_publickey.split('\n')))
                    if key_l and key_l[0] != line_s:
                        message = '%s ssh publickey already changed, please handle it manually!!' % self.request.remote_ip
                        logging.warning(message)
                        send_notify(message)
                    break
            else:
                p = os.popen('''echo "%s" >>%s''' % (client_publickey, known_hosts_path)).read()
                logging.info('%s ssh publickey add!' % self.request.remote_ip)
                if p:
                    logging.info(p)
        # get publickey
        publickey_path = os.path.join(os.path.expanduser('~'), '.ssh/id_rsa.pub')
        with open(publickey_path, 'r') as f:
            self.render_success({"publickey": f.read().replace("\n", "")})


class GetCertHandler(MyRequestHandler):
    @access_auth
    def get(self):
        ret = {}
        cert_path = os.path.join('/etc/letsencrypt/live/', config['domain'])
        if not os.path.exists(cert_path):
            self.render_error('certificate not exist')
            return

        for file_name in os.listdir(cert_path):
            if file_name not in CERT_FILE_NAME_LIST:
                continue
            with open(os.path.join(cert_path, file_name), 'r') as f:
                ret[file_name] = f.read()

        send_notify('%s download certificate' % self.request.remote_ip)
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


def send_notify(message, subject="Certificate Synchronization"):
    from email import encoders
    from email.header import Header
    from email.mime.text import MIMEText
    from email.utils import parseaddr, formataddr
    import smtplib

    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    try:
        msg = MIMEText(message, 'plain', 'utf-8')
        msg['From'] = _format_addr('certbot-async <%s>' % config['smtp_email'])
        msg['To'] = _format_addr(config['notify_receiver'])
        msg['Subject'] = Header(subject, 'utf-8').encode()

        if config['smtp_ssl']:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
    # server.set_debuglevel(1)
        server.login(config['smtp_email'], config['smtp_password'])
        server.sendmail(config['smtp_email'], [config['notify_receiver']], msg.as_string())
        server.quit()
    except Exception as e:
        logging.warning(e)


def certbot_renew():
    from OpenSSL import crypto
    import datetime
    cert_file = '/etc/letsencrypt/live/%s/fullchain.pem' % config['domain']
    if not os.path.exists(cert_file):
        logging.error('certificate not exist')
        send_notify('certificate not exist')
        return
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_file).read())
    not_after_str = cert.get_notAfter().decode('utf-8')
    not_after = datetime.datetime.strptime(not_after_str, '%Y%m%d%H%M%SZ')
    if (not_after - datetime.datetime.now()).days <= 20:
        cmd = "{} renew".format(config['certbot_path']) \
            if config['certbot_path'] else "certbot-auto renew"
        p = os.popen(cmd).read()
        logging.info(p)
        send_notify(p)
        send_cert_for_registration()
    else:
        logging.info("notAfter is %s, renew skipped" % not_after_str)


def init_db():
    import sqlite3
    conn = sqlite3.connect('server.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''create table registration (
                ip varchar(25) primary key,
                user varchar(50),
                ssh_port INTEGER,
                cert_dir varchar(50),
                after_script varchar(250),
                last_timestamp timestamp default (strftime('%s', 'now'))
                )''')
    except Exception as e:
        logging.info(e)
    cursor.close()
    conn.commit()
    conn.close()


def send_cert_for_registration():
    import sqlite3
    import time
    conn = sqlite3.connect('server.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registration;")
    registration_list = cursor.fetchall()

    cert_path = os.path.join('/etc/letsencrypt/live/', config['domain'])
    tmp_dir = os.path.join(BASE_PATH, 'letsencrypt')
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    for file_name in os.listdir(cert_path):
        if file_name not in CERT_FILE_NAME_LIST:
            continue
        with open(os.path.join(cert_path, file_name), 'r') as f:
            _f = open(os.path.join(tmp_dir, file_name), 'w')
            _f.write(f.read())
            _f.close()

    rsync_cmd = "rsync -e 'ssh -p %d' -a ./letsencrypt/ %s@%s:%s"
    script_cmd = '''ssh -p %d  %s@%s "%s"'''
    for reg in registration_list:
        if int(time.time()) - reg[5] > 5184000:
            # last_register_time more than 60 days
            cursor.execute("DELETE FROM registration WHERE ip=?;", (reg[0], ))
            continue

        p = os.popen(rsync_cmd % (reg[2], reg[1], reg[0], reg[3])).read()
        if p:
            logging.info(p)
        p = os.popen(script_cmd % (reg[2], reg[1], reg[0], reg[4])).read()
        if p:
            logging.info(p)
        send_notify('send cert to %s successfully' % reg[0])

    cursor.close()
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r", "--renew", help="Renewal immediately", action="store_true")
    parser.add_argument(
        "-s", "--ssl", help="Use https", action="store_true")
    args = parser.parse_args()

    # Init
    load_config()
    init_log()
    init_db()

    if args.renew:
        certbot_renew()
        logging.info('Renew Finished')
        sys.exit(0)

    # server
    app = make_app()
    ssl_options = {
        "certfile": '/etc/letsencrypt/live/%s/cert.pem' % config['domain'],
        "keyfile": '/etc/letsencrypt/live/%s/privkey.pem' % config['domain'],
    } if args.ssl else None
    server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_options)
    server.listen(config['port'])
    send_notify('certbot-async server starting')
    renew_period_ms = int(86400000 * float(config['renew_period']))
    tornado.ioloop.PeriodicCallback(certbot_renew, renew_period_ms).start()
    tornado.ioloop.IOLoop.current().start()
