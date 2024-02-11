From python:alpine

RUN apk add --update bash curl nano

COPY * /app/

RUN pip install -r /app/requirements.txt

RUN mkdir /config && \
    chmod 777 /config && \
    chmod 777 -R /app

ENTRYPOINT ["/app/entrypoint.sh"]
