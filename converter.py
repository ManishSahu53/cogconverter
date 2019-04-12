import gdal
import numpy as np
import os
import sys
from tqdm import tqdm
import argparse
from daymark import daymark
from src import create_alpha


"""
-co TILED=YES -co COMPRESS=JPEG -co PHOTOMETRIC=YCBCR -co COPY_SRC_OVERVIEWS=YES \
-co BLOCKXSIZE=512 -co BLOCKYSIZE=512 --config GDAL_TIFF_OVR_BLOCKSIZE 512
"""
redisEndPoint = daymark.daymark.getEnvVar("REDIS_ENDPOINT")
redisInstance = daymark.daymark.init(redisEndPoint)
id = daymark.daymark.getEnvVar("JOBID")


class raster():
    intermediate_format = 'VRT'
    path_input = ''
    path_output = ''

    def config(self):
        self.ds = gdal.Open(self.path_input, 1)

        if self.ds is None:
            print('Input file provided %s cannot be loaded' %
                  (self.path_input))
            sys.exit()

        self.no_data = self.ds.GetRasterBand(1).GetNoDataValue()

        if self.no_data is None:
            self.no_data = -9999
            # Reading tif dataset
            # ds = gdal.Open(file)

        # Reading compression type
        try:
            self.compression = self.ds.GetMetadata(
                'IMAGE_STRUCTURE')['COMPRESSION']
        except:
            self.compression = 'LZW'

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
        GDT_Byte 	    Eight bit unsigned integer
        GDT_UInt16 	    Sixteen bit unsigned integer
        GDT_Int16 	    Sixteen bit signed integer
        GDT_UInt32 	    Thirty two bit unsigned integer
        GDT_Int32 	    Thirty two bit signed integer
        GDT_Float32 	Thirty two bit floating point
        GDT_Float64 	Sixty four bit floating point
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


def gdal_addo(raster, dataset):
    # Setting no data value
    for i in range(dataset.RasterCount):
        band = dataset.GetRasterBand(i+1)
        band.SetNoDataValue(raster.no_data)

    # 0 = read-only, 1 = read-write
    overviews = dataset.GetRasterBand(1).GetOverviewCount()
    if overviews == 0:
        gdal.SetConfigOption('COMPRESS_OVERVIEW', 'LZW')
        dataset.BuildOverviews("NEAREST", [2, 4, 8, 16, 32, 64])
        print('Completed: Generating overviews')
    else:
        print('Overviews already generated. Thus skipping!')


def write_blockwise(input_raster, output_raster):
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


def convert2blocksize(path_input, path_output=None):
    '''
    path_input is input file name
    path_output is output file name
    '''
    if path_output is None:
        path_output = os.path.join(path_input, 'index.tif')

    checkdirs(os.path.dirname(path_output))

    print('Input file: %s' % (path_input))
    print('Output file: %s' % (path_output))

    blocksize = 256

    r = raster()
    r.path_input = path_input
    r.path_blockoutput = path_output
    # Loading cnfiguration
    r.config()

    # Checking for projection system
    if len(r.geoprojection) == 0:
        daymark.daymark.logError('TIF not georeferenced', id, redisInstance)

    # Building overviews
    print('Processing: Building overviews')
    r.gdal_addo()

    # Checking alpha bands
    for i in range(r.num_band):
        present = 0
        band = r.ds.GetRasterBand(i+1)
        band_type = band.GetColorInterpretation()
        if int(band_type) == 6:
            present = 1
            print('alpha present')

    if present != 1 and band.DataType == 1 and r.num_band == 3:
        print('alpha band not preset. Adding aplha band...')
        try:
            path_alpha = create_alpha.create_alpha(r)
        except Exception as e:
            daymark.daymark.logError(e, id, redisInstance)

        # Creating tifs
        alpha = raster()
        alpha.path_input = path_alpha
        alpha.path_blockoutput = path_output
        # Loading cnfiguration
        alpha.config()

        # Checking for projection system
        if len(alpha.geoprojection) == 0:
            daymark.daymark.logError(
                'TIF not georeferenced', id, redisInstance)

        # Building overviews
        print('Processing: Building overviews')
        alpha.gdal_addo()

        print('Processing: Creating tiff dataset')
        driver = gdal.GetDriverByName('Gtiff')
        dataset = driver.CreateCopy(alpha.path_blockoutput,
                                    alpha.ds, 0,
                                    ['NUM_THREADS=ALL_CPUS',
                                     'COMPRESS=%s' % (r.compression),
                                     'BIGTIFF=YES',
                                     'TILED=YES',
                                     'BLOCKXSIZE=%d' % (blocksize),
                                     'BLOCKYSIZE=%d' % (blocksize),
                                     'COPY_SRC_OVERVIEWS=YES'])

    else:
        # Creating tifs
        print('Processing: Creating tiff dataset')
        driver = gdal.GetDriverByName('Gtiff')
        dataset = driver.CreateCopy(r.path_blockoutput,
                                    r.ds, 0,
                                    ['NUM_THREADS=ALL_CPUS',
                                     'COMPRESS=%s' % (r.compression),
                                     'BIGTIFF=YES',
                                     'TILED=YES',
                                     'BLOCKXSIZE=%d' % (blocksize),
                                     'BLOCKYSIZE=%d' % (blocksize),
                                     'COPY_SRC_OVERVIEWS=YES'])
    # driver = gdal.GetDriverByName('Gtiff')
    # dataset = driver.Create(r.path_blockoutput,
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

    ''' 
    No need to copy data again. Since we are using CreateCopy() function, it will automatically copy all the datasets
    '''

    # # Copying data from input raster to output raster blockwise
    # write_blockwise(input_raster=r, output_raster=dataset)

    '''
    No Need to build overviews of output raster. It will remove COG properties from TIF
    '''

    # # Building overviews of output dataset
    # print('Processing: Building overviews of output dataset')
    # gdal_addo(r, dataset)
    dataset.FlushCache()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-P', '--payload',
                        help='Pass input file', required=True)

    args = parser.parse_args()
    path_input = args.payload
    convert2blocksize(path_input)
    sys.exit()
