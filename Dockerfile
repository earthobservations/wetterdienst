FROM python:3.7.7-slim
MAINTAINER Daniel Lassahn <daniel.lassahn@meteointelligence.de>

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

COPY ./requirements.txt /opt/requirements.txt
RUN pip install -r /opt/requirements.txt

WORKDIR /app

ENV PYTHONPATH /app/