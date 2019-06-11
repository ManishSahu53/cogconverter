import os
import osr
import json
import utm
import gdal
import datetime


# Metadata class
class Metadata(object):

    def __init__(self, payload):
        self.payload = payload

    # Check directory
    def checkdirs(self, output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(os.path.relpath(output_folder))

    # saving to JSON
    def tojson(self, dictA, file_json):
        with open(file_json, 'w') as f:
            json.dump(dictA, f, indent=4, separators=(',', ': '))

    # EPSG Code to Zone number
    def code2zone(self, epsg_code):
        epsg_code = int(epsg_code)
        last = int(repr(epsg_code)[-1])
        sec_last = int(repr(epsg_code)[-2])
        zone = sec_last*10 + last
        return zone

    # Get EPSG code
    def get_code(self, dataset):
        proj = osr.SpatialReference(wkt=dataset.GetProjection())
        return proj.GetAttrValue('AUTHORITY', 1)

    # Get Bounding Box
    def GetExtent(self, ds, row, col):
        gt = ds.GetGeoTransform()

        originX = gt[0]
        originY = gt[3]
        px_width = gt[1]
        px_height = gt[5]

        epsg = self.get_code(ds)

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
    def extract(self):
        metadata = {}
        ds_geo = gdal.Warp('', self.payload, dstSRS='EPSG:4326', format='VRT')

        ds = gdal.Open(self.payload)

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
        bbox = self.GetExtent(ds_geo, row, col)

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
        metadata['epsgcode'] = self.get_code(ds)
        metadata['originx'] = originX
        metadata['originy'] = originY
        metadata['pixelwidth'] = px_width
        metadata['pixelheight'] = px_height
        metadata['size'] = [col, row]
        metadata['nodata'] = no_data
        metadata['datatype'] = str(arr[0][0].dtype)
        metadata['file'] = os.path.basename(self.payload)
        metadata['time'] = timestamp
        metadata['timesource'] = time_source

        return metadata