"""Product generation functions.
"""

# Imports


from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.nddata.utils import Cutout2D
from astropy.wcs import WCS


# Functions


def make_stamp(
    path: Path,
    image: np.ndarray,
    wcs: WCS,
    position: SkyCoord,
    image_size: int,
    headers_dict: dict[str, int | float] | None = None,
):
    """Create the stamp for a single object.

    A stamp is a 2D square cutout of an object (galaxy or cluster) from its
    original observation image.

    When successful, the stamp is written to disk.

    Parameters
    ----------
    path : Path
        Path to which to write stamp FITS file.
    image : ndarray
        2D float image data array from input science file.
    wcs : WCS
        Coordinate system object from input science file.
    position : SkyCoord
        Coordinates of object in sky.
    image_size : int
        Number of pixels along one dimension of square stamp.
    headers_dict : dict[str, int | float] | None, optional
        Extra headers to store in stamp, as a dict from key to value, by default
        None (don't add any non-WCS headers).

    Raises
    ------
    ValueError
        Cutout missing nonzero data or non-square dimensions (likely on the edge
        of the original image).
    """
    # Generate stamp
    stamp = Cutout2D(data=image, position=position, size=image_size, wcs=wcs)

    # Get nonzero and shape correctness of stamp
    max_zero_fraction = 0.75
    zero_ratio = len(np.where(stamp.data <= 0.0)[0]) / len(stamp.data.flatten())
    stamp_has_nonzero_data = zero_ratio <= max_zero_fraction
    stamp_is_correct_shape = stamp.data.shape == (image_size, image_size)

    # Write stamp to disk if image nonzero and of correct shape
    if stamp_has_nonzero_data and stamp_is_correct_shape:
        # Store headers fromm WCS and passed dict
        stamp_headers = stamp.wcs.to_header()
        if headers_dict is not None:
            for header, value in headers_dict.items():
                stamp_headers[header] = value

        # Write stamp to FITS file
        stamp_hdul = fits.PrimaryHDU(data=stamp.data, header=stamp_headers)
        stamp_hdul.writeto(path, overwrite=True)

    # Otherwise raise error to skip object
    elif not stamp_has_nonzero_data:
        raise ValueError(f"zero pixels {int(zero_ratio * 100)}% of stamp")
    else:
        raise ValueError(f"dimensions {stamp.data.shape} non-square")
