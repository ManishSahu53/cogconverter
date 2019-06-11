import gdal
import numpy as np
import os


def gdal_addo(dataset):
    # Setting no data value
    for i in range(dataset.RasterCount):
        band = dataset.GetRasterBand(i+1)

    # 0 = read-only, 1 = read-write
    overviews = dataset.GetRasterBand(1).GetOverviewCount()
    if overviews == 0:
        gdal.SetConfigOption('COMPRESS_OVERVIEW', 'LZW')
        dataset.BuildOverviews("NEAREST", [2, 4, 8, 16, 32, 64])
        print('Completed: Generating overviews')
    else:
        print('Overviews already generated. Thus skipping!')


def remap_array(arr):
    """
    Remapping [4, 256,256] to [256,256, 4]
    """
    return np.moveaxis(arr, 0, 2)


def create_alpha(raster):
    r = raster
    blocksize = 256
    # Creating a copy in mem
    path_alpha = os.path.join(os.path.dirname(r.path_input), 'alpha.tif')

    # Creating a copy in mem

    vrt_ds = gdal.GetDriverByName('mem').CreateCopy('', r.ds, 0)

    print('Number of bands : %s' % (vrt_ds.RasterCount))
    vrt_ds.AddBand()
    vrt_ds.GetRasterBand(4).SetColorInterpretation(gdal.GCI_AlphaBand)

    print('Processing: Creating alpha tiff dataset')

    driver = gdal.GetDriverByName('Gtiff')
    dataset = driver.CreateCopy(path_alpha,
                                vrt_ds, 0,
                                ['NUM_THREADS=ALL_CPUS',
                                 'COMPRESS=%s' % (r.compression),
                                 'BIGTIFF=YES',
                                 'TILED=YES',
                                 'BLOCKXSIZE=%d' % (blocksize),
                                 'BLOCKYSIZE=%d' % (blocksize),
                                 'COPY_SRC_OVERVIEWS=YES'])

    vrt_ds = None

    output_band = dataset.GetRasterBand(4)

    # block_x, block_y = input_band.GetBlockSize()
    block_x, block_y = 256, 256

    size_x = r.ds.RasterXSize
    size_y = r.ds.RasterYSize

    for x in range(0, int(size_x), int(block_x)):
        if x + block_x < size_x:
            col = block_x
        else:
            col = size_x - x

        for y in range(0, int(size_y), int(block_y)):
            if y + block_y < size_y:
                row = block_y
            else:
                row = size_y - y

            array = r.ds.ReadAsArray(x, y, col, row)
            all_zeros = array != 0
            zeros_image = remap_array(all_zeros)
            mask = np.all(zeros_image, axis=2) * 255
            output_band.WriteArray(mask, x, y)

    print('Added extra band, Number of bands : %s' % (dataset.RasterCount))

    # Creating alpha pyramids
    print('Generating alpha Overviews')
    gdal_addo(dataset)
    print('Saving to Disk')
    dataset.FlushCache()
    dataset = None
    return path_alpha
