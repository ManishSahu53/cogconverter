FROM ubuntu:bionic

# Update base container install
RUN apt-get update
RUN apt-get upgrade -y

# Install GDAL dependencies
RUN apt-get install -y python3-pip libgdal-dev locales

# Install dependencies for other packages
RUN apt-get install gcc g++
#RUN apt-get install jpeg-dev zlib-dev

# Ensure locales configured correctly
RUN locale-gen en_US.UTF-8
ENV LC_ALL='en_US.utf8'

# Set python aliases for python3
RUN echo 'alias python=python3' >> ~/.bashrc
RUN echo 'alias pip=pip3' >> ~/.bashrc

# Update C env vars so compiler can find gdal
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# This will install latest version of GDAL
RUN apt-get -y install python3-gdal
RUN apt-get -y install zip

# Copy function to a path
RUN mkdir -p /var/cogconverter
COPY . /var/cogconverter/

# Work Directory
WORKDIR /var/cogconverter/

# Build context
ADD cogconverter/validator.py cogconverter/converter.py cogconverter/src /

# Install dependencies for tiling
RUN pip3 install -r requirements.txt
RUN python3 setup.py build
RUN python3 setup.py install
    
ENV PYTHONUNBUFFERED = '1'


