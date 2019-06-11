import sys
from osgeo import gdal
import argparse
import converter

import requests
import logging
import os

import osr
import json
import utm
import time
import datetime
from shutil import copy2

start_time = time.time()


# Check directory
def checkdirs(output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(os.path.relpath(output_folder))


# Generate metadata
def get_metadata(payload, processedDir):

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

        # Get band statistics
        bands = {}
        for i in range(num_band):
            dic = {}
            data = []
            data = ds.GetRasterBand(i+1).GetStatistics(0, 1)
            dic['min'] = data[0]
            dic['max'] = data[1]
            dic['mean'] = data[2]
            dic['std'] = data[3]
            bands['b%s' % (i)] = dic

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
        metadata['cogeo'] = True
        metadata['url'] = payload
        metadata['statistics'] = bands

        return metadata

    # Running main function
    metadata = extract(payload)

    # Creating directory if not present
    checkdirs(processedDir)

    # Output file
    output_file = os.path.join(processedDir, 'metadata.json')
    tojson(metadata, output_file)

####################################################################


class ValidateCloudOptimizedGeoTIFFException(Exception):
    pass


def validate(ds, check_tiled=True):
    """Check if a file is a (Geo)TIFF with cloud optimized compatible structure.

    Args:
      ds: GDAL Dataset for the file to inspect.
      check_tiled: Set to False to ignore missing tiling.

    Returns:
      A tuple, whose first element is an array of error messages
      (empty if there is no error), and the second element, a dictionary
      with the structure of the GeoTIFF file.

    Raises:
      ValidateCloudOptimizedGeoTIFFException: Unable to open the file or the
        file is not a Tiff.
    """

    if int(gdal.VersionInfo('VERSION_NUM')) < 2020000:
        raise ValidateCloudOptimizedGeoTIFFException(
            'GDAL 2.2 or above required')

    unicode_type = type(''.encode('utf-8').decode('utf-8'))
    if isinstance(ds, (str, unicode_type)):
        gdal.PushErrorHandler()
        ds = gdal.Open(ds)
        gdal.PopErrorHandler()
        if ds is None:
            raise ValidateCloudOptimizedGeoTIFFException(
                'Invalid file : %s' % gdal.GetLastErrorMsg())
        if ds.GetDriver().ShortName != 'GTiff':
            raise ValidateCloudOptimizedGeoTIFFException(
                'The file is not a GeoTIFF')

    details = {}
    errors = []
    warnings = []
    filename = ds.GetDescription()
    main_band = ds.GetRasterBand(1)
    ovr_count = main_band.GetOverviewCount()
    filelist = ds.GetFileList()
    if filelist is not None and filename + '.ovr' in filelist:
        errors += [
            'Overviews found in external .ovr file. They should be internal']

    if main_band.XSize >= 512 or main_band.YSize >= 512:
        if check_tiled:
            block_size = main_band.GetBlockSize()
            if block_size[0] == main_band.XSize and block_size[0] > 1024:
                errors += [
                    'The file is greater than 512xH or Wx512, but is not tiled']

        if ovr_count == 0:
            warnings += [
                'The file is greater than 512xH or Wx512, it is recommended '
                'to include internal overviews']

    ifd_offset = int(main_band.GetMetadataItem('IFD_OFFSET', 'TIFF'))
    ifd_offsets = [ifd_offset]
    if ifd_offset not in (8, 16):
        errors += [
            'The offset of the main IFD should be 8 for ClassicTIFF '
            'or 16 for BigTIFF. It is %d instead' % ifd_offsets[0]]
    details['ifd_offsets'] = {}
    details['ifd_offsets']['main'] = ifd_offset

    for i in range(ovr_count):
        # Check that overviews are by descending sizes
        ovr_band = ds.GetRasterBand(1).GetOverview(i)
        if i == 0:
            if (ovr_band.XSize > main_band.XSize or
                    ovr_band.YSize > main_band.YSize):
                errors += [
                    'First overview has larger dimension than main band']
        else:
            prev_ovr_band = ds.GetRasterBand(1).GetOverview(i - 1)
            if (ovr_band.XSize > prev_ovr_band.XSize or
                    ovr_band.YSize > prev_ovr_band.YSize):
                errors += [
                    'Overview of index %d has larger dimension than '
                    'overview of index %d' % (i, i - 1)]

        if check_tiled:
            block_size = ovr_band.GetBlockSize()
            if block_size[0] == ovr_band.XSize and block_size[0] > 1024:
                errors += [
                    'Overview of index %d is not tiled' % i]

        # Check that the IFD of descending overviews are sorted by increasing
        # offsets
        ifd_offset = int(ovr_band.GetMetadataItem('IFD_OFFSET', 'TIFF'))
        ifd_offsets.append(ifd_offset)
        details['ifd_offsets']['overview_%d' % i] = ifd_offset
        if ifd_offsets[-1] < ifd_offsets[-2]:
            if i == 0:
                errors += [
                    'The offset of the IFD for overview of index %d is %d, '
                    'whereas it should be greater than the one of the main '
                    'image, which is at byte %d' %
                    (i, ifd_offsets[-1], ifd_offsets[-2])]
            else:
                errors += [
                    'The offset of the IFD for overview of index %d is %d, '
                    'whereas it should be greater than the one of index %d, '
                    'which is at byte %d' %
                    (i, ifd_offsets[-1], i - 1, ifd_offsets[-2])]

    # Check that the imagery starts by the smallest overview and ends with
    # the main resolution dataset
    block_offset = main_band.GetMetadataItem('BLOCK_OFFSET_0_0', 'TIFF')
    if not block_offset:
        errors += ['Missing BLOCK_OFFSET_0_0']
    data_offset = int(block_offset) if block_offset else None
    data_offsets = [data_offset]
    details['data_offsets'] = {}
    details['data_offsets']['main'] = data_offset
    for i in range(ovr_count):
        ovr_band = ds.GetRasterBand(1).GetOverview(i)
        data_offset = int(ovr_band.GetMetadataItem('BLOCK_OFFSET_0_0', 'TIFF'))
        data_offsets.append(data_offset)
        details['data_offsets']['overview_%d' % i] = data_offset

    if data_offsets[-1] < ifd_offsets[-1]:
        if ovr_count > 0:
            errors += [
                'The offset of the first block of the smallest overview '
                'should be after its IFD']
        else:
            errors += [
                'The offset of the first block of the image should '
                'be after its IFD']
    for i in range(len(data_offsets) - 2, 0, -1):
        if data_offsets[i] < data_offsets[i + 1]:
            errors += [
                'The offset of the first block of overview of index %d should '
                'be after the one of the overview of index %d' %
                (i - 1, i)]
    if len(data_offsets) >= 2 and data_offsets[0] < data_offsets[1]:
        errors += [
            'The offset of the first block of the main resolution image'
            'should be after the one of the overview of index %d' %
            (ovr_count - 1)]

    return warnings, errors, details


"""
-co TILED=YES -co COMPRESS=JPEG -co PHOTOMETRIC=YCBCR -co COPY_SRC_OVERVIEWS=YES \
-co BLOCKXSIZE=512 -co BLOCKYSIZE=512 --config GDAL_TIFF_OVR_BLOCKSIZE 512
"""


def main():
    """Return 0 in case of success, 1 for failure."""

    filename = path_input

    if filename is None:
        raise('Error: No input file is given. Exiting...')

    try:
        ret = 0
        warnings, errors, _ = validate(filename)
        if warnings:
            print('The following warnings were found:')
            for warning in warnings:
                print(' - ' + warning)
            print('')
            print('Converting to cloud optimized GeoTIFF')
            converter.convert2blocksize(filename, path_output)

        elif errors:
            print('%s is NOT a valid cloud optimized GeoTIFF.' % filename)
            print('The following errors were found:')
            for error in errors:
                print(' - ' + error)
            print('')
            print('Converting to cloud optimized GeoTIFF')
            converter.convert2blocksize(filename, path_output)
            ret = 1
        else:
            print('%s is a valid cloud optimized GeoTIFF' % filename)
            copy2(filename, path_output)

    except ValidateCloudOptimizedGeoTIFFException as e:
        print('%s is NOT a valid cloud optimized GeoTIFF : %s' %
              (filename, str(e)))

        print('Converting to cloud optimized GeoTIFF')
        converter.convert2blocksize(filename, path_output)
        ret = 1

    return ret


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--payload',
                        help='Pass input file', required=True)
    parser.add_argument('-o', '--output',
                        help='Pass output file',
                        default=None,
                        required=False)


    args = parser.parse_args()
    path_input = args.payload
    path_output = args.output

    if path_output is None:
        path_output = os.path.join(os.path.dirname(path_input), 'index.tif')

    print('Output file is : ' + path_output)

    # Converting starts here
    try:
        main()
        print('Success: Completed')
    except Exception as e:
        raise('Error: Unable to validate and convert. %s' % e)
    sys.exit()