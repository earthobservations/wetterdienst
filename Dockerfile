FROM python:3.8.6-slim
MAINTAINER Daniel Lassahn <daniel.lassahn@meteointelligence.de>

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

RUN pip install poetry==1.0.10

COPY . /app
WORKDIR /app

RUN poetry install
ENV PYTHONPATH /app
