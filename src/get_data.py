import sys
import argparse
import requests
import logging
import os
import errno
import boto3
import botocore
from daymark import daymark
import zipfile
import subprocess
import shutil
from requests_toolbelt.multipart.encoder import MultipartEncoder
import osr
import json
import utm
import time
import datetime

# redisEndPoint = daymark.daymark.getEnvVar("REDIS_ENDPOINT")
# global redisInstance


def uploadFolderToS3(outputBucket, localDirectory, outputKey):

    # local_directory, bucket, destination = sys.argv[1:4]
    try:
        client = boto3.client('s3')
        bucket = outputBucket

        # enumerate local files recursively

        for root, dirs, files in os.walk(localDirectory):

            for filename in files:

                # construct the full local path
                localPath = os.path.join(root, filename)

                # construct the full Dropbox path
                relativePath = os.path.relpath(localPath, localDirectory)

                KEY = outputKey + relativePath

                # relative_path = os.path.relpath(os.path.join(root, filename))

                print('Searching "%s" in "%s"' % (KEY, bucket))
                try:
                    client.head_object(Bucket=bucket, Key=KEY)
                    print("Path found on S3! Skipping %s..." % KEY)

                except:
                    print("Uploading %s..." % KEY)
                    client.upload_file(localPath, bucket, KEY)

    except Exception as e:
        daymark.daymark.logError(e, id, redisInstance)


def downloadFromS3(inputBucket, key, orthoName):

    try:
        BUCKET_NAME = inputBucket
        KEY = key
        filepath = "/lighthouse/" + orthoName
        s3 = boto3.resource('s3')
        try:
            s3.Bucket(BUCKET_NAME).download_file(KEY, filepath)
        except botocore.exceptions.ClientError as e:
            if(e.response['Error']['Code'] == "404"):
                print("The object does not exist.")
            else:
                raise
    except Exception as e:
        daymark.daymark.logError(e, id, redisInstance)


def get_metadata(payload, processedDir):

    # Check directory
    def checkdirs(output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(os.path.relpath(output_folder))

    # saving to JSON
    def tojson(dictA, file_json):
        with open(file_json, 'w') as f:
            json.dump(dictA, f, indent=4, separators=(',', ': '))

    # EPSG Code to Zone number
    def code2zone(epsg_code):
        epsg_code = int(epsg_code)
        last = int(repr(epsg_code)[-1])
        sec_last = int(repr(epsg_code)[-2])
        zone = sec_last*10 + last
        return zone

    # Get EPSG code
    def get_code(dataset):
        proj = osr.SpatialReference(wkt=dataset.GetProjection())
        return proj.GetAttrValue('AUTHORITY', 1)

    # Get Bounding Box
    def GetExtent(ds, row, col):
        gt = ds.GetGeoTransform()

        originX = gt[0]
        originY = gt[3]
        px_width = gt[1]
        px_height = gt[5]

        epsg = get_code(ds)

        max_x = originX + col*px_width
        max_y = originY
        min_x = originX

        if px_height < 0:
            # Since value of height is negative
            min_y = originY + row*px_height

        if px_height > 0:
            # Since value of height is negative
            min_y = originY - row*px_height

    #    if int(epsg) != 4326:
    #        zone = code2zone(epsg)
    #        mini = utm.to_latlon(min_x, min_y, zone, zone_letter='N')
    #        maxi = utm.to_latlon(max_x, max_y, zone, zone_letter='N')

    #    else:
        mini = [min_y, min_x]
        maxi = [max_y, max_x]

        return [mini[1], mini[0], maxi[1], maxi[0]]

    # Extracting metadata
    def extract(payload):
        metadata = {}
        ds_geo = gdal.Warp('', payload, dstSRS='EPSG:4326', format='VRT')

        ds = gdal.Open(payload)

        num_band = ds.RasterCount

        # Checking array type
        banddata = ds.GetRasterBand(1)
        arr = banddata.ReadAsArray(0, 0, 1, 1)

        # Dimensions
        col = ds.RasterXSize
        row = ds.RasterYSize

        # Tranformation settings
        geotransform = ds.GetGeoTransform()

        # Getting Nodata values
        no_data = ds.GetRasterBand(1).GetNoDataValue()

        # Origin and pixel length
        originX = geotransform[0]
        originY = geotransform[3]
        px_width = geotransform[1]
        px_height = geotransform[5]

        # Generate bbox in latitude and longitude only
        bbox = GetExtent(ds_geo, row, col)

        # Getting time information
        try:
            import ntplib
            x = ntplib.NTPClient()
            timestamp = str(datetime.datetime.utcfromtimestamp(
                x.request('europe.pool.ntp.org').tx_time))
            time_source = 'internet'
        except:
            print('Could not sync with time server. Taking Local TimeStamp')
            timestamp = str(datetime.datetime.utcnow()).split('.')[0]
            time_source = 'local'

        # Generating metadata
        metadata['bbox'] = bbox
        metadata['numband'] = num_band
        metadata['epsgcode'] = get_code(ds)
        metadata['originx'] = originX
        metadata['originy'] = originY
        metadata['pixelwidth'] = px_width
        metadata['pixelheight'] = px_height
        metadata['size'] = [col, row]
        metadata['nodata'] = no_data
        metadata['datatype'] = str(arr[0][0].dtype)
        metadata['file'] = os.path.basename(payload)
        metadata['time'] = timestamp
        metadata['timesource'] = time_source

        return metadata

    # Running main function
    metadata = extract(payload)

    # Creating directory if not present
    checkdirs(processedDir)

    # Output file
    output_file = os.path.join(processedDir, 'metadata.json')
    tojson(metadata, output_file)
