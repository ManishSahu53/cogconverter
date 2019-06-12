# COG

## Introduction
It validates the TIF and convert it into COG compliant using gdal. Following are the Use-Cases kept in mind while designing:

1. Large TIF that cannot be fit into memory
2. Reading data block by block, so can be run of even low memory server
3. Supports Multiband TIFs
4. 3-4 Band uint8 TIF (Orthomosaic)
5. Building pyramids if not available (This will improve rendering speed)
6. Compressing data 
7. Compressing to the same compression format as the original TIF. If original TIF was not compressed then LZW lossless compression is used to compress.
8. Tile whole into 256x256 smaller blocks internally

### Validator.py
It will validate tiff for COG format.

### Converter.py
It has the actual converter function which converts tifs into COG format

## To-Do
1. Multi-core processing for faster results.

## How to Run
1. Inside python console

```
import cogconverter as cog
import gdal

path_tif = 'sentinel2.tif'
path_output = 'sentinel2_cog.tif'

coordinate = 'EPSG:4326'
intermediate_foramt = 'VRT'

# If data is in TIF format
ds = gdal.Open(path)

<!-- If data is in another format, JP2 and other format have litte unknown issues, so we are following this pipeline to convert is into first VRT then procesing. -->

ds = gdal.Warp('', path, dstSRS=coordinate, format=intermediate_foramt)

ds1 = cog.converter.convert2blocksize(ds, path_output)
ds1.FlushCache()
ds1 = None
ds = None
```

You can also run it as following.
```
python converter.py -p data/non_cog.tif -o data/cog.tif

python validator.py -p data/cog.tif
```