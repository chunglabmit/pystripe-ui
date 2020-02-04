# PyStripe-UI - a user interface for PyStripe

[PyStripe](https://github.com/chunglabmit/pystripe) is a
program for destriping images produced by SPIM microscopes.
Part of the procedure involves optional image intensity
correction using a "Flat" file - an image file that captures
the intensity differences across the field of view in the
Y direction. In our lab's microscope setup, stacks to be
stitched are stored in subdirectories and given names,
`../<x-pos>/<x-pos>_<y-pos>/z-pos.raw` where <x-pos>,
<y-pos> and <z-pos> are the stage positions of the
acquisition in tenths of a micron.

**pystripe-ui** displays one plane of these files, stitched
together and corrected using one of the available flat-files
per each stack. These can be micro-adjusted in the Y direction
to match the position of the flat file to the position of
the stack. At the end of the user adjustment, the user
saves a series of scripts, one per acquisition channel.
These scripts can then be run to produce the adjusted files.

The following is the command format:

```bash
usage: pystripe-ui [-h] [--flat-files FLAT_FILES]
                   [--xy-voxel-size XY_VOXEL_SIZE]
                   [--z-voxel-size Z_VOXEL_SIZE] [--output-dir OUTPUT_DIR]
                   [--pystripe-args PYSTRIPE_ARGS]
                   image_dir [image_dir ...]

positional arguments:
  image_dir             The root directory of the microscope image files. This
                        may be specified multiple times. The first directory
                        in the list will be the one that is displayed in the
                        UI.

optional arguments:
  -h, --help            show this help message and exit
  --flat-files FLAT_FILES
                        Glob expression to collect the flat files that might
                        be used to perform illumination correction, e.g. "/mnt
                        /cephfs/SmartSPIM_CEPH/IlluC_asset/FLAT_*_101519.tif".
                        The default is /mnt/cephfs/SmartSPIM_CEPH/IlluC_asset/
                        pystripe_flats/*.tif
  --xy-voxel-size XY_VOXEL_SIZE
                        Size of one voxel in the X and Y direction in microns
  --z-voxel-size Z_VOXEL_SIZE
                        Size of one voxel in the Z direction in microns
  --output-dir OUTPUT_DIR
                        Output directory for scripts and pystripe output.
                        Default is parent directory to first image directory.
  --pystripe-args PYSTRIPE_ARGS
                        Argument flags for Pystripe (hint, remember to put
                        quotes around them). Default is "--sigma1 256 --sigma2
                        256 --wavelet db5 --crossover 10".
```

## Installation

This package requires PyQt5, but PyQt5 can either be installed
via Anaconda or pip, but not both - putting PyQt5 in the
requirements will destroy your Anaconda environment, so
we did not do it.

Please install PyQt5 before installing this package.