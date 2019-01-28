# certbot-async

该项目是一个Letsencrypt证书续租及服务器间同步程序，目的是为泛域名证书在一台服务器上申请，其他需要证书的服务器自动同步。

## 服务端

在启动服务端程序之前，首先要使用[certbot](https://certbot.eff.org)成功申请证书。参考以下链接及官方文档：

[https://www.hi-linux.com/posts/6968.html](https://www.hi-linux.com/posts/6968.html)


将项目克隆到`/root/certbot-asnyc`，如在其他位置需自行修改命令参数

该服务须以管理员权限运行，因为Letsencrypt目录的用户为root。如果root用户没有生成过ssh key，还需先使用`ssh-keygen`生成公钥。

在项目下创建`server_config.json`来配置相关设置，可选配置参数：

```json
{
    "domain": "xxx.xx",  // 申请证书的域名，如 xubiaosunny.online
    "certbot_path": "",  // certbot-auto 文件位置，建议将其放入/usr/bin下
    "certbot_auth_hook": "./authenticator_demo.sh",  // 认证钩子脚本
    "renew_period": 10,  // 续租周期，默认10天尝试续租一次
    "port": 8000,  // 服务监听端口
    "access_key": "",  // 认证key
    // 配置邮箱以便通知续租情况，可不配置
    "smtp_server": "", // 邮箱服务器地址
    "smtp_port": "",  // 邮箱服务器端口
    "smtp_ssl": true,  // 是否启用SSL
    "smtp_email": "",  // 邮箱地址
    "smtp_password": "",  // 邮箱密码
    "notify_receiver": "" // 接收通知的邮箱
}
```

在项目下创建`whitelist.txt`以启用在白名单功能，将允许访问的ip一行一个写入文件内。删除该文件则所有ip均可访问。

服务端启动可选参数：

```
-r, --renew  直接续租，不启动服务
-s, --ssl    使用https启动服务，默认使用http
```

认证钩子：

续租的时候也需要DNS认证或者文件认证（貌似范域名只可以DNS认证），所以需要自动化脚本添加DNS记录（TXT）。官方文档及示例：

[https://certbot.eff.org/docs/using.html#pre-and-post-validation-hooks](https://certbot.eff.org/docs/using.html#pre-and-post-validation-hooks)

一个哥们对接了几个厂商的API（aliyun/tencentyun/godaddy），可以直接拿来用：

[https://github.com/ywdblog/certbot-letencrypt-wildcardcertificates-alydns-au](https://github.com/ywdblog/certbot-letencrypt-wildcardcertificates-alydns-au)

### Docker启动

首先安装docker

```shell
sudo apt-get update
sudo apt-get install docker-ce
```

构建镜像

```shell
docker build --rm -f "Dockerfile" -t certbot-async:latest .
```

启动容器

```shell
docker run -d -it \
-v /root/certbot-async:/root/certbot-asnyc \
-v /etc/letsencrypt:/etc/letsencrypt \
-v /root/.ssh:/root/.ssh \
-p 8000:8000 \
--rm --name certboot-async certbot-async python ./server.py
```

### 使用python3直接启动

由于我使用pypthon3.7开发，若没有python3.7环境，则需安装

```
wget https://www.python.org/ftp/python/3.7.2/Python-3.7.2.tar.xz && \
    tar -xvf Python-3.7.2.tar.xz && \
    cd Python-3.7.2 && \
    ./configure && make && sudo make install
```

安装`pipenv`

```shell
python3 -m pip install pipenv
```

安装依赖

```shell
pipenv install
```

启动服务程序

```shell
pipenv run python ./server.py
```

## 客户端

在项目下创建`client_config.json`来配置相关设置，可选配置参数

```json
{
    "server_host": "http://127.0.0.1:8000", // 服务端地址
    "access_key": "",  // 认证key，需与服务端一样
    "cert_dir": "./letsencrypt",  // 证书存放位置
    "after_script": "echo $HOME",  // 获取证书后执行的命令 
    "ssh_port": "22" // 本地ssh端口
}
```

客户端有两种工作模式：

### 主动模式

直接从服务端下载证书文件

```
pipenv run python ./client.py
```

### 订阅模式

```
pipenv run python ./client.py -rs
```
订阅后，服务端续租成功后会自动将证书同步到客户端服务器，讲求实时性。订阅有效期为60天。须在60天内再次订阅，逾期服务端将不会同步。

