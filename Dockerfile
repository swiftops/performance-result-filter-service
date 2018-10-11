FROM python:alpine

WORKDIR /usr/src/app
COPY requirements.txt ./

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install blinker

COPY . .

EXPOSE 8086

CMD ["gunicorn", "--config", "gunicorn_config.py", "services:app"]