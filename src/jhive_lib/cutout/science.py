"""TODO
"""

# Imports


from pathlib import Path
from typing import Annotated


import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.nddata.utils import Cutout2D
from astropy.wcs import WCS
from pydantic import BaseModel, StringConstraints


# Classes


class FICL(BaseModel):
    """Configuration model for a single FICL.

    FICL is an abbreviation for the field, image version, catalog version, and
    filter of a JWST science observation. Each FICL corresponds to a single
    observation.

    Attributes
    ----------
    field : str
        Field of observation, e.g. "abell2744clu".
    image_version : str
        Version string of JWST image processing, e.g. "grizli-v7.2".
    catalog_version : str
        Version string of JWST cataloging, e.g. "dja-v7.2".
    filter : str
        Observational filter band, e.g. "f140w".
    objects : list[int]
        Integer IDs of galaxies or cluster targets in catalog.
    pixscale : tuple[float, float]
        Pixel scale along x and y axes, in arcseconds per pixel.

    Notes
    -----
    All strings are converted to lowercase upon validation.
    """

    field: Annotated[str, StringConstraints(to_lower=True)]
    image_version: Annotated[str, StringConstraints(to_lower=True)]
    catalog_version: Annotated[str, StringConstraints(to_lower=True)]
    filter: Annotated[str, StringConstraints(to_lower=True)]
    objects: list[int]
    pixscale: tuple[float, float]

    def __str__(self) -> str:
        return "_".join(
            [self.field, self.image_version, self.catalog_version, self.filter]
        )


# Functions


## File


def get_fits_data(
    path: Path, hdu: str | int = "PRIMARY"
) -> tuple[np.ndarray, fits.Header]:
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
    tuple[np.ndarray, fits.Header]
        The image as a 2D float array, and its corresponding header object.
    """
    # Open FITS file
    fits_file = fits.open(path)

    # Get data and headers from file
    image, headers = fits_file[hdu].data, fits_file[hdu].header

    # Close file and return
    fits_file.close()
    return image, headers


## Calculation


def get_central_flux(
    image: np.ndarray, pixscale: tuple[int, int], zeropoint: float
) -> float:
    """Calculate the flux per pixel of an object at its center (peak).

    Parameters
    ----------
    image : ndarray
        Observation cutout of object, as a 2D float array.
    pixscale : tuple[int, int]
        Pixel scale along x-axis and y-axis of the image, in arcseconds/pixel.
    zeropoint : float
        Zeropoint of the observation, in AB magnitude.

    Returns
    -------
    float
        Surface brightness of the object at its center.
    """
    # Get location of center of image
    center = int(image.shape[0] / 2)

    # If image size is odd, get 9 center pixels, otherwise 4
    odd_flag = image.shape[0] % 2

    # Get total flux and area across center pixels
    total_flux = np.sum(
        image[
            center - 1 : center + 1 + odd_flag,
            center - 1 : center + 1 + odd_flag,
        ]
    )
    total_area = ((2 + odd_flag) ** 2) * pixscale[0] * pixscale[1]

    # Get flux per pixel
    flux_per_pixel = total_flux / total_area

    # Return zeroed log of flux per pixel
    return np.nan_to_num(-2.5 * np.log10(flux_per_pixel) + zeropoint)
