
# Non Macbook M1 chip
FROM selenium/standalone-chrome

# Macbook M1 chip
# FROM seleniarm/standalone-chromium 

# chose  wd / working directory, for docker image
WORKDIR /usr/app
COPY . ./

USER root
RUN chmod 777 /usr/app/src/scraper/data/logs/journal_data.txt
RUN sudo apt-get -y update
RUN sudo apt-get install -y software-properties-common
RUN sudo apt-get install -y python3-pip
RUN sudo apt-get install -y libpq-dev

# Non Macbook M1 chip
RUN pip3 install -r requirements.txt

# Macbook M1 chip
# RUN pip3 install --break-system-packages -r requirements.txt

CMD ["sh", "-c", "python3 ./src/main.py"]
