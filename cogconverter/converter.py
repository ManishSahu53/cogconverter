try:
    import osgeo
except:
    raise('osgeo not found. You can install using - conda install gdal. Else use docker file given at repo')
try:
    import gdal
except:
    raise('gdal not found. You can install using - conda install gdal. Else use docker file given at repo')

import numpy as np
import os
import sys
from tqdm import tqdm
import argparse
from cogconverter.config import default_config
from cogconverter.src import pyramid

"""
-co TILED=YES -co COMPRESS=JPEG -co PHOTOMETRIC=YCBCR -co COPY_SRC_OVERVIEWS=YES \
-co BLOCKXSIZE=512 -co BLOCKYSIZE=512 --config GDAL_TIFF_OVR_BLOCKSIZE 512
"""


class raster(object):

    def __init__(self, ds):
        self.intermediate_format = 'VRT'
        self.ds = ds
        self.config()

    def config(self):
        if self.ds is None:
            raise('Input file provided %s cannot be loaded' %
                  (self.ds))

        self.no_data = self.ds.GetRasterBand(1).GetNoDataValue()

        if self.no_data is None:
            self.no_data = default_config.NO_DATA
            # Reading tif dataset
            # ds = gdal.Open(file)

        # Reading compression type
        try:
            self.compression = self.ds.GetMetadata(
                'IMAGE_STRUCTURE')['COMPRESSION']
        except:
            self.compression = default_config.COMPRESS

        if self.compression.upper() == 'YCbCr JPEG'.upper():
            self.compression = 'JPEG'

        # Reading number of bands
        self.num_band = self.ds.RasterCount

        # Defining dtype
        self.dtype = self.ds.ReadAsArray(0, 0, 1, 1).dtype

        # Dimensions
        self.col = self.ds.RasterXSize
        self.row = self.ds.RasterYSize

        # Tranformation settings
        self.geotransform = self.ds.GetGeoTransform()

        # Projections
        self.geoprojection = self.ds.GetProjection()

        # Check for pyramids and overviews, 0 if no overviews
        self.overview = self.ds.GetRasterBand(1).GetOverviewCount()

        # # Origin and pixel length
        # self.originX = self.geotransform[0]
        # self.originY = self.geotransform[3]
        # self.px_width = self.geotransform[1]
        # self.px_height = self.geotransform[5]

        # # Generate bbox of original raster
        # self.bbox, self.origin = self.ds.GetExtent()

    def dtype_conversion(self):
        """
        GDT_Byte 	    8 bit unsigned integer
        GDT_UInt16 	    16 bit unsigned integer
        GDT_Int16 	    16 bit signed integer
        GDT_UInt32 	    32 bit unsigned integer
        GDT_Int32 	    32 bit signed integer
        GDT_Float32 	32 bit floating point
        GDT_Float64 	64 bit floating point
        """
        # Float 64
        if self.dtype == np.dtype(np.float64):
            output_dtype = gdal.GDT_Float64
            return output_dtype
        # Float 32
        elif self.dtype == np.dtype(np.float32):
            output_dtype = gdal.GDT_Float32
            return output_dtype
        # Uint 8
        elif self.dtype == np.dtype(np.uint8):
            output_dtype = gdal.GDT_Byte
            return output_dtype
        # Uint 16
        elif self.dtype == np.dtype(np.uint16):
            output_dtype = gdal.GDT_UInt16
            return output_dtype
        # Unit 32
        elif self.dtype == np.dtype(np.uint32):
            output_dtype = gdal.GDT_UInt32
            return output_dtype
        # Int 16
        elif self.dtype == np.dtype(np.int16):
            output_dtype = gdal.GDT_Int16
            return output_dtype
        # Int 32
        elif self.dtype == np.dtype(np.int32):
            output_dtype = gdal.GDT_Int32
            return output_dtype
        else:
            return gdal.GDT_Float32

    def gdal_addo(self):
        # 0 = read-only, 1 = read-write.
        if self.overview == 0:
            gdal.SetConfigOption('COMPRESS_OVERVIEW', 'LZW')
            self.ds.BuildOverviews("NEAREST", [2, 4, 8, 16, 32, 64])
            print('Completed: Generating overviews')
        else:
            print('Overviews already generated. Thus skipping!')

# Class over
######################################################################


def write_blockwise(input_raster, output_raster):

    assert isinstance(input_raster, raster), __name__ + \
        'Excepted raster class type'

    dimension = input_raster.num_band

    for num_band in range(dimension):
        print('Processing: Band %d' % (num_band))
        input_band = input_raster.ds.GetRasterBand(num_band+1)
        output_band = output_raster.GetRasterBand(num_band+1)
        block_x, block_y = input_band.GetBlockSize()
        # block_x, block_y = 5000, 5000

        size_x = input_band.XSize
        size_y = input_band.YSize

        for x in tqdm(range(0, int(size_x), int(block_x))):
            if x + block_x < size_x:
                col = block_x
            else:
                col = size_x - x

            for y in range(0, int(size_y), int(block_y)):
                if y + block_y < size_y:
                    row = block_y
                else:
                    row = size_y - y

                array = input_band.ReadAsArray(x, y, col, row)
                output_band.WriteArray(array, x, y)
                del array


def checkdirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


def convert2blocksize(ds, path_output):
    '''
    path_input is input file name
    path_output is output file name
    '''
    assert isinstance(ds, osgeo.gdal.Dataset), __name__ + \
        'Excepted osgeo.gdal class type'

    blocksize = default_config.BLOCKSIZE

    r = raster(ds)
    # Loading cnfiguration
    r.config()

    # Checking for projection system
    if len(r.geoprojection) == 0:
        raise('Error: GeoProjection of input file is not defined')

    # Building overviews
    print('Processing: Building overviews')
    r.gdal_addo()

    # Creating tifs
    print('Processing: Creating tiff dataset')
    driver = gdal.GetDriverByName('Gtiff')
    try:
        dataset = driver.CreateCopy(path_output,
                                    r.ds, 0,
                                    ['NUM_THREADS=ALL_CPUS',
                                     'COMPRESS=%s' % (r.compression),
                                     'BIGTIFF=YES',
                                     'TILED=YES',
                                     'BLOCKXSIZE=%d' % (blocksize),
                                     'BLOCKYSIZE=%d' % (blocksize),
                                     'COPY_SRC_OVERVIEWS=YES'])
    except Exception as e:
        raise('Error: Unable to process %s' % e)

    print('Success: Creating tiff dataset completed')
    return dataset
    # driver = gdal.GetDriverByName('Gtiff')
    # dataset = driver.Create(path_output,
    #                         r.col, r.row, r.num_band,
    #                         r.dtype_conversion(), ['NUM_THREADS=ALL_CPUS',
    #                                                'COMPRESS=%s' % (
    #                                                    r.compression),
    #                                                'BIGTIFF=YES',
    #                                                'TILED=YES',
    #                                                'BLOCKXSIZE=%d' % (
    #                                                    blocksize),
    #                                                'BLOCKYSIZE=%d' % (
    #                                                    blocksize),
    #                                                'COPY_SRC_OVERVIEWS=YES'])
    # dataset.SetGeoTransform(r.geotransform)
    # dataset.SetProjection(r.geoprojection)

    # '''
    # No need to copy data again. Since we are using CreateCopy() function, it will automatically copy all the datasets
    # '''

    # # Copying data from input raster to output raster blockwise
    # write_blockwise(input_raster=r, output_raster=dataset)

    # '''
    # No Need to build overviews of output raster. It will remove COG properties from TIF
    # '''

    # # # Building overviews of output dataset, this will remove COG nature of TIF
    # print('Processing: Building overviews of output dataset')
    # addo = pyramid.pyramid(dataset)
    # addo.gdal_addo()
    # print('Success: Creating tiff dataset completed')
    # return dataset


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--payload',
                        help='Pass input file',
                        required=True)

    parser.add_argument('-o', '--output',
                        help='Pass output file',
                        default=None,
                        required=False)

    args = parser.parse_args()
    path_input = args.payload
    path_output = args.output

    # Standard parameters
    coordinate = default_config.EPSG_CRS
    intermediate_format = default_config.INTERMEDIATE_FORMAT

    # Reading raster
    # ds = gdal.Open(path_input)
    if not os.path.exists(path_input):
        raise('Error: File not found')
    
    ds = gdal.Warp('', path_input, dstSRS=coordinate,
              format=intermediate_format)

    ds1 = convert2blocksize(ds, path_output)
    ds = None
    try:
        print('Processing: Flushing')
        ds1.FlushCache()
        ds1 = None
        print('Success: Process Completed')
    except Exception as e:
        raise('Error: Unable to save to %s %s' % (path_output, e))

    sys.exit()
