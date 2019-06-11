import gdal
import osgeo
from cogconverter.config import default_config


# Creating pyramids/overviews
class pyramid(object):
    def __init__(self, dataset):
        self.dataset = dataset
        assert isinstance(dataset, osgeo.gdal.Dataset), __name__ + 'Excepted osgeo.gdal class type'


    def gdal_addo(self):
        # Setting no data value
        for i in range(self.dataset.RasterCount):
            band = self.dataset.GetRasterBand(i+1)
            band.SetNoDataValue(default_config.NO_DATA)

        # 0 = read-only, 1 = read-write
        overviews = self.dataset.GetRasterBand(1).GetOverviewCount()
        if overviews == 0:
            gdal.SetConfigOption('COMPRESS_OVERVIEW', default_config.COMPRESS)
            self.dataset.BuildOverviews(default_config.RESAMPLING, [2, 4, 8, 16, 32, 64])
            print('Completed: Generating overviews')
        else:
            print('Overviews already generated. Thus skipping!')
