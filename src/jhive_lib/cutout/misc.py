"""Miscellaneous utility functions.
"""

# Imports


from pathlib import Path
from datetime import datetime

import numpy as np
from astropy.table import Table
from tqdm import tqdm

from . import header


# Functions


## Primitive


def get_str_from_datetime(date_time: datetime) -> str:
    """Get a string representation of a datetime, in the format
    'YYYYMMDDTHHMMSS'.

    Parameters
    ----------
    date_time : datetime
        Datetime to convert to str.

    Returns
    -------
    str
        String representation of datetime.
    """
    return date_time.strftime("%Y%m%dT%H%M%S")


def get_str_from_process_id(process_id: int) -> str:
    """Get a string representation of a process ID, in the format '001', with
    two leading zeroes.

    Parameters
    ----------
    process_id : int
        Number to convert to string.

    Returns
    -------
    str
        Process ID as string with leading zeroes.
    """
    return str(process_id).rjust(3, "0")


def get_str_from_pixscale(pixscale: tuple[int, int]) -> str:
    """Get a pixel scale as a string.

    Parameters
    ----------
    pixscale : tuple[int,int]
        Pixel scale along x and y axes, respectively, in arcseconds per pixel.

    Returns
    -------
    str
        Pixel scale as a string, in milli-arcseconds per pixel (only expressing
        'mas').
    """
    # Get maximum pixel scale from pair
    max_pixscale = np.nanmax(pixscale)

    # Return pixel scale in milli-arcseconds, as a str
    return str(round(max_pixscale * 1000)) + "mas"


def get_unique(items: list) -> list:
    """Get the unique elements in a list of elements, as a sorted list.

    Parameters
    ----------
    items : list
        List of elements to be sorted.

    Returns
    -------
    list
        Sorted list of unique elements.
    """
    not_nan_items = []

    # Remove any NaNs from list
    for item in items:
        if isinstance(item, float) and np.isnan(item):
            continue
        else:
            not_nan_items.append(item)

    # Return unique items in list, sorted
    return sorted(set(not_nan_items))


## Array


def get_cropped(image: np.ndarray, size: int) -> np.ndarray:
    """Get a crop (centered cutout) of an image to a sub-radius within the
    image.

    Parameters
    ----------
    image : np.ndarray
        Image data, as a 2D array.
    size : int
        Length of square image.

    Returns
    -------
    np.ndarray
        Cropped image.
    """
    # Return current image if image size unchanged
    if (image.shape[0] == image.shape[1]) and (image.shape[0] == size):
        return image

    # Get index of central pixel and number of pixels in half-image
    center = int(image.shape[0] / 2)
    radius = int(size / 2)

    # Get and return cropped image
    cropped_image = image[
        center - radius : center + radius + 1, center - radius : center + radius + 1
    ]
    return cropped_image


def get_linear_normalized(
    data: np.ndarray,
    min_i: float | None = None,
    max_i: float | None = None,
    min_f: float = 0.0,
    max_f: float = 1.0,
    dtype: type = float,
) -> np.ndarray:
    """Get a numpy array normalized to a minimum and maximum.

    Parameters
    ----------
    data : np.ndarray
        Array to be normalized.
    min_i : float | None, optional
        Initial data minimum, by default None (auto).
    max_i : float | None, optional
        Initial data maximum, by default None (auto).
    min_f : float, optional
        Final data minimum, by default 0.
    max_f : float, optional
        Final data maximum, by default 1.
    dtype : type, optional
        Data type of normalized array, by default float.

    Returns
    -------
    np.ndarray
        Array normalized from 0 to 1.
    """
    # Get initial min and max if not passed
    if min_i is None:
        min_i = np.nanmin(data)
    if max_i is None:
        max_i = np.nanmax(data)
    if max_i == min_i:
        max_i += 1

    # Return rescaled data
    return np.array(
        (data - min_i) / (max_i - min_i) * (max_f - min_f) + min_f, dtype=dtype
    )


## Path


def get_path_object(path: str | Path, resolve: bool = True) -> Path:
    """Get a Path object pointing to `path`.

    Parameters
    ----------
    path : str | Path
        Path to file or directory.
    resolve : bool, optional
        Resolve the full path to this object, by default True.

    Returns
    -------
    Path
        Path object representing this path.
    """
    # Get Path object if passed string
    if isinstance(path, str):
        path_object = Path(path)
    else:
        path_object = path

    # Return resolved path if passed
    if resolve:
        return path_object.resolve()
    else:
        return path_object


def get_alternate_filter_names(filter: str) -> list[str]:
    """Get a list of alternate filter names for a filter.

    Attempts to match any of the following filter name formats.
    1. f200w-clear
    2. f200w-clearp
    3. clear-f200w
    4. clearp-f200w
    5. f200w
    6. 200

    Parameters
    ----------
    filter : str
        Unresolved filter name.

    Returns
    -------
    list[str]
        List of possible alternate filter names.
    """

    return [
        filter,
        f"{filter}-clear",
        f"{filter}-clearp",
        f"clear-{filter}",
        f"clearp-{filter}",
        f"f{filter}m",
        f"f{filter}w",
        f"f{filter}n",
        filter.split("-")[0],
        filter.split("-")[-1],
        filter.split("-"),
    ]


def get_alternate_end_tags() -> list[str]:
    """Get a list of alternate end tags for a FIL file.

    The following files are FIL (field, image version, filter) files, and have
    an end tag before their respective labels.
    1. Exposure Map (`exp`)
    2. Science (`sci`)
    3. Weights Map (`wht`)

    An end tag is `drc` or `drz`.

    Returns
    -------
    list[str]
        List of known end tags.
    """
    return ["drc", "drz"]


# FICLO TODO maybe move to class


def clean_filter(filter: str) -> str:
    # Get cleaned filter name
    if "-" in filter:
        filters = filter.split("-")
        filter = filters[1] if "clear" in filters[0] else filters[0]

    return filter


def get_objects(
    path: Path,
    process_id: int,
    process_count: int,
    objects: list[int] | None,
    first_object: int | None,
    last_object: int | None,
    ingest_flags: Table | None = None,
    filter: str | None = None,
) -> list[int]:
    """Get a list of objects for a FICL, as a list of integer IDs from the
    corresponding photometric catalog.

    Parameters
    ----------
    path : Path
        Path to photometric catalog.
    process_count : int
        Number of processes in batch.
    process_id : int
        ID of process in batch.
    objects : list[int] | None, optional
        List of object IDs, by default None.
        Note this setting overrides the first and last object settings.
    first_object : int | None, optional
        ID of first object in batch, by default None.
    last_object : int | None, optional
        ID of last object in batch, by default None.
    ingest_flags : Table | None, optional
        Catalog flagging objects to be ingested into J-HIVE, by default None.
    filter : str | None, optional
        Name of filter of objects which to ingest, by default None.

    Returns
    -------
    list[int]
        List of object IDs corresponding to the 'id' key in the FICL's
        photometric catalog.
    """
    # Set base objects as all possible objects if not specifically listed
    if objects is None:
        # Get all possible objects from photometric catalog
        sorted_objects = sorted(header.ids(path))

        # Remove all objects before first object
        if first_object is not None:
            while sorted_objects[0] < first_object:
                sorted_objects.pop(0)

        # Remove all objects after last object
        if last_object is not None:
            while sorted_objects[-1] > last_object:
                sorted_objects.pop()

    # Set base objects if specifically listed
    else:
        sorted_objects = sorted(objects)

    # Get list of objects flagged for ingest
    if ingest_flags is not None:
        # Get wavelength band from both filters
        filter_split = filter.split("-")
        band = filter_split[1 if "clear" in filter_split[0] else 0]

        # Skip if filter is missing from ingest catalog
        # TODO temporary - ingest all objects marked for visualization
        flag_header = f"ingest_viz"
        # flag_header = f"ingest_{band}"
        if flag_header not in ingest_flags:
            pass

        # Iterate over each object and ingest if flagged
        else:
            ingest_objects = []
            for object in objects:
                if ingest_flags[ingest_flags["id"] == object][flag_header]:
                    ingest_objects.append(object)
            sorted_objects = ingest_objects

    # Get start index from base count and process settings
    total_object_count = len(sorted_objects)
    start = process_id * (total_object_count // process_count)
    start += min(process_id, total_object_count % process_count)

    # Get stop index from start index and expected count
    object_count = total_object_count // process_count
    object_count += process_id < (total_object_count % process_count)
    stop = start + object_count

    # Return list of objects for this process
    return sorted_objects[start:stop]


def get_object_loop(objects: list[int], progress_bar: bool = False) -> tqdm | list[int]:
    """Get a list-like object of object IDs over which to iterate, i.e. a TQDM
    object if progress is displayed, and the list of objects otherwise.

    Parameters
    ----------
    objects : list[int]
        List of object IDs over which to iterate.
    progress_bar : bool, optional
        Display progress as a loading bar, by default False.

    Returns
    -------
    tqdm | list[int]
        List-like object over which to iterate for program runs.
    """
    return tqdm(iterable=objects, unit="obj", leave=False) if progress_bar else objects
