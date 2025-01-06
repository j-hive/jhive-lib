"""Retrieve data from scientific header, catalog, FITS, and other file formats.
"""

# Imports


from pathlib import Path
from typing import Any

import numpy as np
from numpy import ndarray
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.io.fits import Header
from astropy.table import Table

from . import science, misc


# Constants


# TODO move

DEFAULT_PIXSCALE = 0.04
"""Default pixel scale, 40mas/pixel.
"""


PHOTOMETRY_ZEROPOINT = 23.9
"""AB zeropoint for fluxes from the DJA photometric catalogs.
"""


APERTURE_1_RADIUS = 0.25
"""Radius of aperture 1, in arcseconds, corresponding to retrieving
'filter_corr_1' for flux.

See Also
--------
https://dawn-cph.github.io/dja/blog/2023/07/14/photometric-catalog-demo/
    Other aperture radii, under 'Photometric apertures'.
"""


# Functions


## FITS


def read(path: Path, hdu: int | str = "PRIMARY") -> tuple[ndarray, Header]:
    """Get the image data and headers from a FITS file.

    Closes the file so the limit of open files is not encountered.

    Parameters
    ----------
    path : Path
        Path to FITS file.
    hdu : int | str, optional
        Index in HDU list at which to retrieve HDU, by default "PRIMARY".

    Returns
    -------
    tuple[ndarray, Header]
        The image as a 2D float array, and its corresponding header object.
    """
    # Open FITS file
    fits_file = fits.open(path)
    fits_hdu: fits.PrimaryHDU = fits_file[hdu]

    # Get data and headers from file
    image, headers = fits_hdu.data, fits_hdu.header

    # Close file and return
    fits_file.close()
    return image, headers


def zeropoint(headers: Header) -> float:
    """Get the instrumental zeropoint magnitude of an observation from its
    corresponding headers, in priority of
    1. Zeropoint stored under `ZP` key
    2. AB magnitude from `PHOTFLAM` and `PHOTPLAM` keys
    3. ST magnitude from `PHOTFLAM` key

    Parameters
    ----------
    headers : Header
        Header object.

    Returns
    -------
    float
        Instrumental zeropoint magnitude.

    Raises
    ------
    ValueError
        No zeropoint keys found in Header object.
    """
    # Return stored zeropoint
    if "ZP" in headers:
        return headers["ZP"]

    # Return AB zeropoint
    elif ("PHOTFLAM" in headers) and ("PHOTPLAM" in headers):
        return science.ab_zeropoint(
            photflam=headers["PHOTFLAM"], photplam=headers["PHOTPLAM"]
        )

    # Return ST zeropoint
    elif "PHOTFLAM" in headers:
        return science.st_zeropoint(photflam=headers["PHOTFLAM"])

    # Raise error if no relevant keys
    else:
        raise ValueError("no zeropoint keys found in header")


def pixscale(headers: Header) -> tuple[float, float]:
    """Get the pixel scale of an observation from its FITS file, in arcsec / px
    along the x and y axes, respectively.

    Used because not every frame has the same pixel scale. For the most
    part, long wavelength filtered observations have scales of 0.04"/px,
    and short wavelength filters have scales of 0.02"/px.

    Parameters
    ----------
    headers : Header
        Header object.

    Returns
    -------
    tuple[float, float]
        Pixel scale along the x and y axes, respectively, in arcsec / px.

    Raises
    ------
    KeyError
        Coordinate transformation matrix element headers missing from frame.
    """
    # Get pixel scale if directly set as header
    if "PIXELSCL" in headers:
        pixscale_str = headers["PIXELSCL"]

        # Try to get pixel scale from header as float
        try:
            pixscale = float(pixscale_str)
            return (pixscale, pixscale)

        # Try to get pixel scale from header as string
        except:
            try:
                pixscale = float(pixscale_str.split("mas")) * 1e-3
                return (pixscale, pixscale)

            # Other formats unknown
            except:
                raise ValueError(f"pixel scale {pixscale_str} unrecognized")

    # Get pixel scale from coordinate matrix headers if not set as header
    else:
        # Raise error if keys not found in header
        if any(
            [header not in headers for header in ["CD1_1", "CD2_2", "CD1_2", "CD2_1"]]
        ):
            raise KeyError(f"missing coordinate matrix headers")

        # Calculate and set pixel scales
        pixscale_x = np.sqrt(headers["CD1_1"] ** 2 + headers["CD1_2"] ** 2) * 3600
        pixscale_y = np.sqrt(headers["CD2_1"] ** 2 + headers["CD2_2"] ** 2) * 3600
        return (pixscale_x, pixscale_y)


def integrated_magnitude(headers: Header) -> float:
    """Get the integrated magnitude of an object from its corresponding Header
    object.

    Parameters
    ----------
    headers : Header
        Header object.

    Returns
    -------
    float
        Integrated magnitude of this object.
    """
    return headers["IM"]


def surface_brightness(headers: Header) -> float:
    """Get the surface brightness of an object from its corresponding Header
    object.

    Parameters
    ----------
    headers : Header
        Header object.

    Returns
    -------
    float
        Surface brightness of this object.
    """
    return headers["SB"]


## DJA Photometric Catalog


def ids(path: Path) -> list[int]:
    """Get all the integer object IDs in a DJA photometric catalog, as a list of
    integers.

    Parameters
    ----------
    path : Path
        Path to DJA photometric catalog FITS file.

    Returns
    -------
    list[int]
        List of all integer object IDs in a DJA photometric catalog.
    """
    # Read DJA photometric catalog
    input_catalog = Table.read(path)

    # Return list of integer IDs
    return [int(id) for id in input_catalog["id"]]


def row(catalog: Table, object: int) -> Table:
    """Get the data row of an object from a DJA photometric catalog.

    Parameters
    ----------
    catalog : Table
        DJA photometric catalog.
    object : int
        Integer object ID.

    Returns
    -------
    Table
        Data row of object in DJA photometric catalog, if it is found.
    """
    return catalog[catalog["id"] == object]


def datum(row: Table, key: str, type: type) -> Any:
    """Get a casted datum from a DJA photometric catalog row.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.
    key : str
        Key in DJA photometric catalog, i.e. column name.
    type : type
        Type of datum, to which to cast.

    Returns
    -------
    Any
        Casted datum from data row.
    """
    return type(row[key])


def position(row: Table) -> SkyCoord:
    """Get the position of an object, as a SkyCoord object.

    Parameters
    ----------
    row : Table
        Data row of object in a DJA photometric catalog.

    Returns
    -------
    SkyCoord
        Position of object, as a SkyCoord object.
    """
    return SkyCoord(
        ra=datum(row, "ra", float), dec=datum(row, "dec", float), unit="deg"
    )


def flux(row: Table, filter: str) -> float:
    """Get the integrated flux of an object within an effective radius, in uJy.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.
    filter : str
        Filter from which to get flux of object.

    Returns
    -------
    float
        Integrated flux of object, in uJy.
    """
    # TODO
    return datum(row, f"{misc.clean_filter(filter)}_corr_1", float)


def flux_radius(row: Table) -> float:
    """Get the flux radius of an object, in arcseconds.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.

    Returns
    -------
    float
        Flux radius of object, in arcsec.
    """
    return datum(row, "flux_radius", float)


def kron_radius(row: Table) -> float:
    """Get the Kron radius of an object, in pixels.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.

    Returns
    -------
    float
        Kron radius of object.
    """
    return datum(row, "kron_radius", float)


def semi_major_axis(row: Table) -> float:
    """Get the semi-major axis of an object, in pixels.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.

    Returns
    -------
    float
        Semi-major axis of object.
    """
    return datum(row, "a_image", float)


def semi_minor_axis(row: Table) -> float:
    """Get the semi-minor axis of an object, in pixels.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.

    Returns
    -------
    float
        Semi-minor axis of object.
    """
    return datum(row, "b_image", float)


def axis_ratio(row: Table) -> float:
    """Get the axis ratio of an object.

    Parameters
    ----------
    row : Table
        Data row of object in DJA photometric catalog.

    Returns
    -------
    float
        Axis ratio of object.
    """
    return semi_minor_axis(row) / semi_major_axis(row)
