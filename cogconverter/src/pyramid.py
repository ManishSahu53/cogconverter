import gdal

# Creating pyramids/overviews


class pyramid(object):
    def __init__(self, dataset):
        self.dataset = dataset
        self.param = {'method': 'NEAREST', 'compression': 'LZW'}


    def gdal_addo(self):
        # # Setting no data value
        # for i in range(self.dataset.RasterCount):
        #     band = self.dataset.GetRasterBand(i+1)

        # 0 = read-only, 1 = read-write
        overviews = self.dataset.GetRasterBand(1).GetOverviewCount()
        if overviews == 0:
            gdal.SetConfigOption('COMPRESS_OVERVIEW', self.param['compression'])
            self.dataset.BuildOverviews(self.param['method'], [2, 4, 8, 16, 32, 64])
            print('Completed: Generating overviews')
        else:
            print('Overviews already generated. Thus skipping!')
