"""Convert and calculate scientific parameters.
"""

# Imports


import numpy as np


# Functions


## Conversion


def arcsec_to_px(distance: float, pixscale: float) -> float:
    """Convert a distance in arcseconds to pixels.

    Parameters
    ----------
    distance : float
        Distance, in arcsec.
    pixscale : float
        Pixel scale, in arcsec / px.

    Returns
    -------
    float
        Distance, in px.
    """
    return distance / pixscale


def px_to_arcsec(distance: float, pixscale: float) -> float:
    """Convert a distance in pixels to arcseconds.

    Parameters
    ----------
    distance : float
        Distance, in px.
    pixscale : float
        Pixel scale, in arcsec / px.

    Returns
    -------
    float
        Distance, in arcsec.
    """
    return distance * pixscale


def image_size(radius: float, scale: float, minimum: int) -> int:
    """Calculate the square pixel dimension of an object's image, from a
    characteristic radius and scale, in px.

    Parameters
    ----------
    radius : float
        Characteristic radius of object, in px.
    scale : float
        Multiplicative scale factor.
    minimum : int
        Minimum image size, in px.


    Returns
    -------
    int
        Number of pixels in each edge of a square image containing this object.
    """
    # Calculate image size from scale factor
    image_size = int(radius * scale)

    # Return maximum between calculated and minimum image size
    return np.nanmax([image_size, minimum])


## Calculation


def ab_zeropoint(photflam: float, photplam: float) -> float:
    """Calculate the AB instrumental zeropoint magnitude, at which one count per
    second is produced [1]_.

    Parameters
    ----------
    photflam : float
        Inverse sensitivity, i.e. the scaling factor necessary to transform an
        instrumental flux in units of electrons per second to a physical flux
        density, in erg / (A * electron * cm^2).
    photplam : float
        Pivot wavelength, in A.

    Returns
    -------
    float
        AB instrumental zeropoint magnitude.

    References
    ----------
    .. [1] “Zeropoints.” STScI,
        www.stsci.edu/hst/instrumentation/acs/data-analysis/zeropoints.
    """
    return -2.5 * np.log10(photflam) - 5 * np.log10(photplam) - 2.408


def st_zeropoint(photflam: float) -> float:
    """Calculate the ST instrumental zeropoint magnitude, at which one count per
    second is produced [1]_.

    Parameters
    ----------
    photflam : float
        Inverse sensitivity, i.e. the scaling factor necessary to transform an
        instrumental flux in units of electrons per second to a physical flux
        density, in erg / (A * electron * cm^2).

    Returns
    -------
    float
        ST instrumental zeropoint magnitude.

    References
    ----------
    .. [1] “Zeropoints.” STScI,
        www.stsci.edu/hst/instrumentation/acs/data-analysis/zeropoints.
    """
    return -2.5 * np.log10(photflam) - 21.1


def integrated_magnitude(flux: float, zeropoint: float) -> float:
    """Calculate the integrated magnitude of an object.

    Parameters
    ----------
    flux : float
        Integrated flux across an object's effective radius.
    zeropoint : float
        Zeropoint magnitude for this field.

    Returns
    -------
    float
        Integrated magnitude of the object.

    Raises
    ------
    ValueError
        Negative flux.
    """
    # Raise error if flux negative
    if flux <= 0:
        raise ValueError(f"flux {flux} negative")

    # Calculate and return magnitude from integrated flux, offset by zeropoint
    return -2.5 * np.log10(flux) + zeropoint


def surface_brightness(
    flux: float,
    zeropoint: float,
    radius: float,
    pixscale: float | None = None,
) -> float:
    """Calculate an estimate of the surface brightness of an object.

    Parameters
    ----------
    flux : float
        Integrated flux across an object's effective radius.
    zeropoint : float
        Zeropoint magnitude for this field.
    radius : float
        Characteristic radius of object, in arcsec or px.
    pixscale : float | None, optional
        Pixel scale, in arcsec / px, by default None (radius in arcsec).

    Returns
    -------
    float
        Surface brightness of the object at its center.

    Raises
    ------
    ValueError
        Negative flux.
    """
    # Raise error if flux negative
    if flux <= 0:
        raise ValueError(f"flux {flux} negative")

    # Calculate magnitude from integrated flux, offset by zeropoint
    magnitude = -2.5 * np.log10(flux) + zeropoint

    # Calculate area within radius as squared arcseconds
    radius_in_as = radius * (1 if pixscale is None else pixscale)
    area = np.pi * radius_in_as**2
    offset = 2.5 * np.log10(area)

    # Calculate and return surface brightness as magnitude, offset by area
    return magnitude + offset
