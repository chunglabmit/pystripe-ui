import setuptools

version = "0.1.0"

setuptools.setup(
    name="pystripe-ui",
    version=version,
    description="User interface for pystripe parameters",
    install_requires=[
        "matplotlib",
        "numpy",
        "tifffile",
        "tsv"],
    entry_points={
        "console_scripts": [
           'pystripe-ui=pystripe_ui.main:main'
        ]},
    author="Kwanghun Chung Lab",
    packages=["pystripe_ui"],
    url="https://github.com/chunglabmit/pystripe-ui",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        'Programming Language :: Python :: 3.5',
    ]
)    
