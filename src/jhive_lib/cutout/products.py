"""Product generation functions.
"""

# Imports


from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.nddata.utils import Cutout2D
from astropy.wcs import WCS

from . import science


# Functions


def make_stamp(
    path: Path,
    image: np.ndarray,
    wcs: WCS,
    zeropoint: float,
    pixscale: tuple[int, int],
    position: SkyCoord,
    image_size: int,
    store_key: str | None = None,
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
    zeropoint : float
        Brightness zeropoint from input science file.
    pixscale : tuple[int, int]
        Pixel scales along each axis from input science file, in "/px.
    position : SkyCoord
        Coordinates of object in sky.
    image_size : int
        Number of pixels along one dimension of square stamp.
    store_key : str | None, optional
        Header key to store information on successful fits, by default None
        (N/A).

    Raises
    ------
    NotImplementedError
        Unknown information to store in headers on successful stamp.
    ValueError
        Cutout missing nonzero data or non-square dimensions (likely on the edge
        of the original image).
    """
    # Generate stamp
    stamp = Cutout2D(data=image, position=position, size=image_size, wcs=wcs)

    # Get nonzero and shape correctness of stamp
    stamp_has_nonzero_data = np.amax(stamp.data) > 0
    stamp_is_correct_shape = stamp.data.shape == (image_size, image_size)

    # Write stamp to disk if image nonzero and of correct shape
    if stamp_has_nonzero_data and stamp_is_correct_shape:
        stamp_headers = stamp.wcs.to_header()
        stamp_headers["EXPTIME"] = 1
        stamp_headers["ZP"] = zeropoint

        # Store extra information in headers if requested
        if store_key is not None:
            match store_key:
                case "SB":
                    stamp_headers[store_key] = science.get_central_flux(
                        image=image, pixscale=pixscale, zeropoint=zeropoint
                    )

                case _:
                    raise NotImplementedError(
                        f"'{store_key}' unknown information to store in stamp"
                    )

        # Wrote stamp to FITS file
        stamp_hdul = fits.PrimaryHDU(data=stamp.data, header=stamp_headers)
        stamp_hdul.writeto(path, overwrite=True)

    # Otherwise raise error to skip object
    elif not stamp_has_nonzero_data:
        raise ValueError(f"missing nonzero data")
    else:
        raise ValueError(
            f"got dimensions {stamp.data.shape}, "
            + f"expected ({image_size}, {image_size})"
        )
