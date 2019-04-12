# COG

## Introduction
It validates the TIF and convert it into COG compliant using gdal. Following are the Use-Cases kept in mind while designing:

1. Large TIF that cannot be fit into memory
2. Reading data block by block, so can be run of even low memory server
3. Supports Multiband TIFs
4. 3-4 Band uint8 TIF (Orthomosaic)
5. Consideration of Alpha band For transparency
6. Building pyramids if not available (This will improve rendering speed)
7. Compressing data 
8. Compressing to the same compression format as the original TIF. If original TIF was not compressed then LZW lossless compression is used to compress.
9. Tile whole into 256x256 smaller blocks internally

### Validator.py
It will validate tiff for COG format. If tif is already is in COG format then it will skip that file else it will convert it to COG format.

### Converter.py
It has the actual converter function which converts tifs into COG format

## To-Do
1. Multi-core processing for faster results.

