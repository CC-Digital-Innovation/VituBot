FROM python:3.10-slim

# install curl and jq
RUN apt-get update && apt-get install -y curl jq

# install sops
RUN curl -OL https://github.com/mozilla/sops/releases/download/v3.7.2/sops_3.7.2_amd64.deb \
    && apt-get -y install ./sops_3.7.2_amd64.deb \
    && rm sops_3.7.2_amd64.deb

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD [ "./build-script.sh" ]