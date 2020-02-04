import argparse
import glob
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import \
    FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
import os
from PyQt5.QtWidgets import QSizePolicy, QMainWindow, QMenu, QVBoxLayout, QShortcut
from PyQt5.QtWidgets import QHBoxLayout, QGroupBox, QApplication, QLineEdit
from PyQt5.QtWidgets import QGridLayout, QWidget, QLabel, QSlider, QComboBox
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QKeySequence
from PyQt5 import QtCore
import sys
import tifffile
import time
import traceback
import tsv.raw
import typing

DEFAULT_FLAT_GLOB_EXPR = \
    "/mnt/cephfs/SmartSPIM_CEPH/IlluC_asset/pystripe_flats/*.tif"
DEFAULT_SCRIPT_NAME = "run_pystripe.sh"
DEFAULT_PYSTRIPE_ARGS = "--sigma1 256 --sigma2 256 --wavelet db5 --crossover 10"

def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flat-files",
        help='Glob expression to collect the flat files that might be used '
        'to perform illumination correction, e.g. '
        '"/mnt/cephfs/SmartSPIM_CEPH/IlluC_asset/FLAT_*_101519.tif". The '
        'default is %s ' % DEFAULT_FLAT_GLOB_EXPR,
        default=DEFAULT_FLAT_GLOB_EXPR
    )
    parser.add_argument("--xy-voxel-size",
                        help="Size of one voxel in the X and Y direction in "
                             "microns",
                        type=float,
                        default=1.8)
    parser.add_argument("--z-voxel-size",
                        help="Size of one voxel in the Z direction in microns",
                        type=float,
                        default=2.0)
    parser.add_argument("--output-dir",
                        help="Output directory for scripts and pystripe "
                             "output. Default is parent directory to first "
                             "image directory.")
    parser.add_argument("--pystripe-args",
                        help="Argument flags for Pystripe (hint, remember to "
                        "put quotes around them). Default is \"%s\". " %
                        DEFAULT_PYSTRIPE_ARGS,
                        default=DEFAULT_PYSTRIPE_ARGS)
    parser.add_argument("image_dir",
                        help="The root directory of the microscope image "
                             "files. This may be specified multiple times.",
                        nargs="+")
    return parser.parse_args(args)


class MPLCanvas(FigureCanvas):
    def __init__(self, parent):
        """
        Create the canvas window.

        :param parent: Parent window to this one
        """
        figure = Figure()
        self.axes = figure.add_subplot(1, 1, 1)
        super(MPLCanvas, self).__init__(figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        self.first_display = True

    def show(self,
             img:np.ndarray,
             xcoords:typing.Sequence[int],
             ycoords:typing.Sequence[int]):
        """"""
        high = np.percentile(img, 99)
        if not self.first_display:
            xmin, xmax = self.axes.get_xlim()
            ymin, ymax = self.axes.get_ylim()
            self.axes.cla()
        self.axes.imshow(np.clip(img, 0, high), cmap='gray')
        for xcoord in xcoords:
            self.axes.plot([xcoord, xcoord],
                           [0, img.shape[0]], "r--")
        for ycoord in ycoords:
            self.axes.plot([0, img.shape[1]],
                           [ycoord, ycoord], "r--")
        if not self.first_display:
            self.axes.set_xlim(xmin, xmax)
            self.axes.set_ylim(ymin, ymax)
        else:
            self.first_display = False
        self.axes.set_axis_off()
        self.draw()


def imread(path:str) -> np.ndarray:
    """
    Read an image file
    :param path: path to a .tif or raw file
    :return: the image
    """
    if path.endswith(".raw"):
        return tsv.raw.raw_imread(path)
    else:
        return tifffile.imread(path)


IMAGE_PATHS_TYPE = typing.Dict[typing.Tuple[float, float], typing.Sequence[str]]

def collect_files(directory:str) -> IMAGE_PATHS_TYPE:
    """
    Collect the files in the subdirectories
    :param directory: the root directory of the microscope acquisition.
    The files are in the directory in the format, "X/X_Y/Z.raw"
    :return: a dictionary of stacks where the dictionary indices are the
    X and Y positions of the stacks in microns
    """
    tiff_glob_expr = os.path.join(directory, "*", "*", "*.tif*")
    raw_glob_expr = os.path.join(directory, "*", "*", "*.raw")
    files = sorted(glob.glob(tiff_glob_expr))
    if len(files) == 0:
        files = sorted(glob.glob(raw_glob_expr))
    result = {}
    for file in files:
        x_y = os.path.split(os.path.dirname(file))[1]
        x, y = [float(_) / 10 for _ in x_y.split("_")]
        if (x, y) in result:
            result[x, y].append(file)
        else:
            result[x, y] = [file]
    return result


IMAGE_DIMENSIONS = {}


def get_image_dimensions(path:str) -> typing.Tuple[int, int]:
    """
    Get the dimensions of an image (with cacheing)
    :param path: the path to the image
    :return: a two-tuple of y and x
    """
    if path not in IMAGE_DIMENSIONS:
        y, x = imread(path).shape
        IMAGE_DIMENSIONS[path] = (y, x)
    return IMAGE_DIMENSIONS[path]


def get_x_coords(paths:IMAGE_PATHS_TYPE) -> typing.Sequence[float]:
    """
    Get the X coordinates of the grid of images

    :param paths: a dictionary of x and y coordinates for keys and stacks
    of paths for values
    :return: a sequence of X coordinates for the grid
    """
    return tuple(sorted(set([x for x, y in paths.keys()])))


def get_y_coords(paths:IMAGE_PATHS_TYPE) -> typing.Sequence[float]:
    """
    Get the Y coordinates of the grid of images

    :param paths: a dictionary of x and y coordinates for keys and stacks
    of paths for values
    :return: a sequence of Y coordinates for the grid
    """
    return tuple(sorted(set([y for x, y in paths.keys()])))


class ApplicationWindow(QMainWindow):
    def __init__(self,
                 image_directories:typing.Sequence[str],
                 flat_files:str,
                 voxel_size:typing.Sequence[float],
                 output_dir,
                 pystripe_args):
        """
        Initialize the application window

        :param image_directories: the directories containing images
        :param flat_files: the flat file choices for illumination correction
        :param voxel_size: The size of a voxel in microns in z, y, x format
        """
        QMainWindow.__init__(self)
        self.image_directories = dict([
            (_, collect_files(_)) for _ in image_directories
        ])
        self.flat_files = dict([
            (_, imread(_)) for _ in sorted(glob.glob(flat_files))
        ])
        self.images = {}
        self.voxel_size = voxel_size
        self.output_dir = output_dir
        self.pystripe_args = pystripe_args
        self.init_interface()

    def init_interface(self):
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Pystripe illumination correction")
        self.file_menu = QMenu("&File", self)
        self.file_menu.addAction("&Save", self.fileSave)
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.fileSave)
        self.file_menu.addAction("&Quit", self.fileQuit,
                                 QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)
        self.main_widget = QWidget(self)
        #
        # The layout:
        #  |---------------------------splitter--------------|
        #  | ---------- vbox ------------ |                  |
        #  | |  Z: z-chooser & dark     | |                  |
        #  | | ---------grid----------- | |                  |
        #  | | | 1, 1    |    2, 1    | | |   canvas         |
        #  | | ---------- ------------- | |                  |
        #  | | | 1, 2    |    2, 2    | | |                  |
        #  | | ------------------------ | |                  |
        #  |------------------------------|------------------|
        imgdir = list(self.image_directories.values())[0]
        stackfiles = list(imgdir.values())[0]
        x = get_x_coords(imgdir)
        y = get_y_coords(imgdir)
        splitter = QSplitter(QtCore.Qt.Horizontal)
        top_layout = QHBoxLayout()
        top_layout.addWidget(splitter)
        self.main_widget.setLayout(top_layout)
        vwidget = QWidget()
        vbox = QVBoxLayout(self.main_widget)
        vwidget.setLayout(vbox)
        splitter.addWidget(vwidget)
        zchooser_group_box = QGroupBox("Z plane to display / Dark field value")
        vbox.addWidget(zchooser_group_box)
        chooser_layout = QHBoxLayout()
        zchooser_group_box.setLayout(chooser_layout)
        grid_group_box = QGroupBox("Y offsets and flat files")
        vbox.addWidget(grid_group_box)
        grid = QGridLayout()
        grid.setColumnStretch(1, len(x))
        grid.setColumnStretch(2, len(y))
        grid_group_box.setLayout(grid)
        #
        # -- the Z chooser --
        #
        choices = [_.split(".")[0] for _ in stackfiles]
        if len(choices) > 40:
            # Limit to 20 or so Z
            spacing = len(choices) // 20
            choices = choices[::spacing]
        z_chooser_label = QLabel("Z:")
        chooser_layout.addWidget(z_chooser_label)
        self.z_chooser = QComboBox()
        chooser_layout.addWidget(self.z_chooser)
        for choice in choices:
            self.z_chooser.addItem(os.path.split(choice)[-1])
        self.z_chooser.currentTextChanged.connect(self.onZChange)
        dark_label = QLabel("Dark")
        chooser_layout.addWidget(dark_label)
        self.dark_input = QLineEdit()
        self.dark_input.setText("100")
        chooser_layout.addWidget(self.dark_input)
        self.dark_slider = QSlider(QtCore.Qt.Horizontal)
        self.dark_slider.setMinimum(0)
        self.dark_slider.setMaximum(250)
        self.dark_slider.setValue(100)
        chooser_layout.addWidget(self.dark_slider)
        self.hookSliderAndInput(self.dark_slider, self.dark_input)
        #
        # --- the grid of controls ---
        #
        self.stack_label = {}
        self.stack_flat_file_widget = {}
        self.stack_y_offset_box_widget = {}
        self.stack_y_offset_slider_widget = {}
        for xi in range(len(x)):
            for yi in range(len(y)):
                key = (x[xi], y[yi])
                if key not in imgdir:
                    continue # skip non-existent directory
                stack_group = QGroupBox("%d,%d" % key)
                grid.addWidget(stack_group, yi, xi)
                stack_layout = QVBoxLayout()
                stack_group.setLayout(stack_layout)
                y_layout = QHBoxLayout()
                stack_layout.addLayout(y_layout)
                self.stack_label[key] = QLabel("Y:")
                y_layout.addWidget(self.stack_label[key])
                y_input = QLineEdit()
                y_layout.addWidget(y_input)
                y_input.setText("0")
                y_slider = QSlider(QtCore.Qt.Horizontal)
                y_layout.addWidget(y_slider)
                y_slider.setMinimum(-200)
                y_slider.setMaximum(200)
                self.hookSliderAndInput(y_slider, y_input)
                self.stack_y_offset_box_widget[key] = y_input
                self.stack_y_offset_slider_widget[key] = y_slider
                flat_choices = QComboBox()
                self.stack_flat_file_widget[key] = flat_choices
                stack_layout.addWidget(flat_choices)
                for choice in self.flat_files:
                    filename = os.path.split(choice)[1]
                    flat_choices.addItem(filename)
                flat_choices.currentTextChanged.connect(self.updateDisplay)
        #
        # The display box
        #
        self.canvas = MPLCanvas(self.main_widget)
        self.addToolBar(NavigationToolbar(self.canvas, self))
        splitter.addWidget(self.canvas)
        #
        # Set up main window
        #
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.onZChange()

    def hookSliderAndInput(self, y_slider, y_input):
        def onInputChanged(text, slider=y_slider):
            try:
                value = int(text)
                y_slider.setValue(value)
            except ValueError:
                pass

        y_input.textEdited[str].connect(onInputChanged)

        def onSliderChanged(value, input=y_input):
            y_input.setText(str(value))
            self.updateDisplay()

        y_slider.valueChanged.connect(onSliderChanged)

    def onZChange(self, *args):
        imgdir = list(self.image_directories.values())[0]
        z = self.z_chooser.currentText()
        for x, y in imgdir:
            filename = [_ for _ in imgdir[x, y]
                        if os.path.split(_)[1].startswith(z + ".")]
            if len(filename) > 0:
                self.images[x, y] = imread(filename[0])
        self.updateDisplay()

    def get_flat_file_from_widget(self, widget:QComboBox):
        file_text = widget.currentText()
        key = [_ for _ in self.flat_files
               if os.path.split(_)[1] == file_text][0]
        return self.flat_files[key]

    def updateDisplay(self, *args):
        try:
            t0 = time.time()
            imgdir = list(self.image_directories.values())[0]
            xs = np.array(get_x_coords(imgdir))
            ys = np.array(get_y_coords(imgdir))
            xs_vox = (xs / self.voxel_size[2]).astype(int)
            ys_vox = (ys / self.voxel_size[1]).astype(int)
            some_image = list(self.images.values())[0]
            xshape = xs_vox[-1] - xs_vox[0] + some_image.shape[1]
            yshape = ys_vox[-1] - ys_vox[0] + some_image.shape[0]
            img = np.zeros((yshape, xshape), np.float32)
            dark = self.dark_slider.value()
            for x, y in imgdir:
                xidx = int(x / self.voxel_size[2]) - xs_vox[0]
                yidx = int(y / self.voxel_size[1]) - ys_vox[0]
                subimg = np.maximum(self.images[x, y], dark) - dark
                divisor = self.get_divisor(subimg, x, y)
                img[yidx:yidx+subimg.shape[0], xidx:xidx+subimg.shape[1]] =\
                    subimg / divisor.reshape(divisor.shape[0], 1)
            t1 = time.time()
            print("Image compositing time: %.1f sec" % (t1 - t0))
            t0 = time.time()
            self.canvas.show(img,
                             xs_vox[1:] - xs_vox[0],
                             ys_vox[1:] - ys_vox[0])
            t1 = time.time()
            print("Image display time: %.1f sec" % (t1 - t0))
        except:
            traceback.print_exc()

    def get_divisor(self, subimg, x, y):
        divisor = self.get_flat_file_from_widget(
            self.stack_flat_file_widget[x, y])
        offset = self.stack_y_offset_slider_widget[x, y].value()
        if offset < 0:
            last = divisor[-1, 0]
            y_slop = max(0, subimg.shape[0] - divisor.shape[0] - offset)
            divisor = np.hstack([
                divisor[-offset:, 0],
                np.ones(y_slop, divisor.dtype) * last])
        else:
            first = divisor[0, 0]
            y_slop = max(0, subimg.shape[0] - divisor.shape[0] + offset)
            divisor = np.hstack([
                np.ones(y_slop, divisor.dtype) * first,
                divisor[:divisor.shape[0] - offset, 0]])
        return divisor

    def fileSave(self, event=None):
        flats_dir = os.path.join(self.output_dir, "flats")
        if not os.path.exists(flats_dir):
            os.makedirs(flats_dir)
        written_flats = set()
        for path in self.image_directories:
            command = ""
            output_path = os.path.join(self.output_dir,
                                       os.path.split(path)[-1] + "_destriped")
            stacks = self.image_directories[path]
            for key in stacks:
                x, y = key
                stack_dir = os.path.dirname(stacks[key][0])
                stack_base, stack_xy = os.path.split(stack_dir)
                stack_root, stack_x = os.path.split(stack_base)
                stack_output_path = os.path.join(output_path, stack_x,
                                                 stack_xy)
                flat_name = os.path.join(flats_dir, stack_xy + ".tif")
                if not flat_name in written_flats:
                    typical_img = self.images[x, y]
                    divisor = self.get_divisor(typical_img, x, y)
                    divisor = np.column_stack([divisor] * typical_img.shape[1])
                    tifffile.imsave(flat_name, divisor, compress=3)
                    written_flats.add(flat_name)
                command += """
pystripe --input {stack_dir} \\
         --output {stack_output_path} \\
         --flat {flat_name} \\
         --dark {dark} \\
         {pystripe_args}
""".format(stack_dir=stack_dir,
           stack_output_path=stack_output_path,
           flat_name=flat_name,
           dark=self.dark_slider.value(),
           pystripe_args=self.pystripe_args)
        script_path = os.path.join(path, DEFAULT_SCRIPT_NAME)
        with open(script_path, "w") as fd:
            fd.write(command)
        os.chmod(script_path, 0o775)

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()


def main(args=sys.argv[1:]):
    options = parse_args(args)
    app = QApplication(sys.argv)
    voxel_size = (options.z_voxel_size, options.xy_voxel_size,
                  options.xy_voxel_size)
    if options.output_dir is None:
        output_dir = os.path.dirname(options.image_dir[0])
    else:
        output_dir = options.output_dir
    window = ApplicationWindow(options.image_dir,
                               options.flat_files,
                               voxel_size,
                               output_dir,
                               options.pystripe_args)
    window.setWindowTitle("Pystripe UI")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()