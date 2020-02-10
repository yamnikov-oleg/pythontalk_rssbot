FROM python:3.7-alpine

RUN apk add --no-cache build-base libffi-dev openssl-dev

RUN mkdir /app
WORKDIR /app

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD . .

CMD [ "python", "./rssbot.py" ]
