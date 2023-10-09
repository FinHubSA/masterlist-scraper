
# Non Macbook M1 chip
FROM selenium/standalone-chrome

# Macbook M1 chip
# FROM seleniarm/standalone-chromium 

ENV script ""

# chose  wd / working directory, for docker image
WORKDIR /usr/app
COPY . ./

RUN sudo apt-get -y update
RUN sudo apt-get install -y software-properties-common
RUN sudo apt-get install -y python3-pip

# Non Macbook M1 chip
RUN pip3 install -r requirements.txt

# Macbook M1 chip
# RUN pip3 install --break-system-packages -r requirements.txt

CMD ["sh", "-c", "python3 ./src/${script}"]
