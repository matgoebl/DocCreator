FROM python:3.8-slim-bullseye
COPY requirements.txt /
RUN apt-get update && apt-get install -y git
RUN pip3 install --no-cache-dir --no-build-isolation -r /requirements.txt && rm -f /requirements.txt
RUN adduser --uid 1000 --home /app --no-create-home --disabled-password --gecos User --shell /bin/sh user
COPY src/ /app
RUN mkdir -p /app/work/ && chown -R 1000 /app/work/
ARG BUILDTAG=unknown
ENV BUILDTAG=${BUILDTAG}
RUN echo "${BUILDTAG}" > /app/templates/build.txt
WORKDIR /app
EXPOSE 5000
USER user
CMD gunicorn --bind 0.0.0.0:5000 --access-logfile - --workers 5 app:app
