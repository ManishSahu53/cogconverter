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
RUN mkdir -p /var/cog_converter
COPY . /var/cog_converter/

# Work Directory
WORKDIR /var/cog_converter/

# Build context
ADD validator.py converter.py src /

# Install dependencies for tiling
RUN pip3 install argparse && \
    pip3 install numpy && \
    pip3 install pillow && \
    pip3 install requests_toolbelt && \
    pip3 install boto3 && \
    pip3 install requests && \
    pip3 install daymark && \
    pip3 install utm && \
    pip3 install tqdm && \
    pip3 install --upgrade awscli
    
ENV PYTHONUNBUFFERED = '1'


