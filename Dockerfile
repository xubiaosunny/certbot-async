FROM python:3

WORKDIR /root/certbot-asnyc

COPY Pipfile ./
COPY Pipfile.lock ./
RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

RUN rm Pipfile Pipfile.lock
