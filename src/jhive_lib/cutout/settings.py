"""Settings ingestion and creation utility functions.
"""

# Imports


import shutil
import tempfile
import itertools
import logging
from pathlib import Path
from datetime import datetime
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    StringConstraints,
    NonNegativeInt,
    PositiveInt,
    PositiveFloat,
)

from . import logs, misc, science


# Classes


class FICL(BaseModel):
    """Model representing a single observation science frame.

    Corresponds to the field, image version, catalog version, and filter of the
    frame.

    Attributes
    ----------
    field : str
        Field of observation, as a lowercase string.
    image_version : str
        Image processing version, as a lowercase string.
    catalog_version : str
        Cataloging version, as a lowercase string.
    filter : str
        Filter name, as a lowercase string.
    pixscale : tuple[float, float]
        Pixel scale along x and y axes, respectively, in arcseconds per pixel,
        as a tuple of positive floats.
    objects : list[int]
        Integer IDs of galaxies or cluster targets as listed in this FICL's
        corresponding photometric catalog, as a list of positive integers, by
        default empty.
    failed : list[int]
        Integer IDs of objects which failed to run, as a list of positive
        integers, by default empty.
    """

    field: Annotated[str, StringConstraints(to_lower=True)]
    image_version: Annotated[str, StringConstraints(to_lower=True)]
    catalog_version: Annotated[str, StringConstraints(to_lower=True)]
    filter: Annotated[str, StringConstraints(to_lower=True)]
    pixscale: tuple[PositiveFloat, PositiveFloat]
    objects: list[PositiveInt]
    failed: list[PositiveInt] = []

    def __init__(self, **kwargs):
        # Validate required files
        catalog_path, science_path = kwargs["catalog"], kwargs["science"]
        if (not isinstance(catalog_path, Path)) or (not catalog_path.is_file()):
            raise FileNotFoundError("photometric catalog missing")
        if (not isinstance(science_path, Path)) or (not science_path.is_file()):
            raise FileNotFoundError("science frame missing")

        # Get values for each primitive setting
        field = kwargs.get("field")
        image_version = kwargs.get("image_version")
        catalog_version = kwargs.get("catalog_version")
        filter = kwargs.get("filter")
        objects = kwargs.get("objects")
        process_id = kwargs.get("process_id")
        process_count = kwargs.get("process_count")
        first_object = kwargs.get("first_object")
        last_object = kwargs.get("last_object")

        # Get values for each data setting
        pixscale = science.get_pixscale(path=kwargs["science"])
        ficl_objects = misc.get_objects(
            path=kwargs["catalog"],
            process_id=process_id,
            process_count=process_count,
            objects=objects,
            first_object=first_object,
            last_object=last_object,
        )

        # Initialize dict to unpack
        settings = {
            "field": field,
            "image_version": image_version,
            "catalog_version": catalog_version,
            "filter": filter,
            "pixscale": pixscale,
            "objects": ficl_objects,
        }

        # Initialize instance
        super().__init__(**settings)

    def __str__(self) -> str:
        return "_".join(
            [self.field, self.image_version, self.catalog_version, self.filter]
        )

    def __eq__(self, other) -> bool:
        return (isinstance(other, FICL)) and (str(self) == str(other))

    def to_dict(self) -> dict[str, str | list[int] | tuple[float, float]]:
        """Represent configuration object as a dict.

        Returns
        -------
        dict[str, str | list[int] | tuple[float, float]]
            Representation of configuration object.
        """
        return {
            "field": self.field,
            "image version": self.image_version,
            "catalog version": self.catalog_version,
            "filter": self.filter,
            "pixscale": misc.get_str_from_pixscale(self.pixscale),
            "objects": self.objects,
            "failed": self.failed,
        }

    def remove(self, objects: list[int]):
        """Remove objects from this FICL's configuration.

        Does nothing if an object is not in FICL's list.

        Parameters
        ----------
        objects : list[int]
            Integer IDs of objects to remove from FICL.
        """
        for object in objects:
            try:
                self.objects.remove(object)
                self.failed.append(object)
            except:
                continue


class StageSettings(BaseModel):
    """Stages to run, as flags.

    Attributes
    ----------
    setup : bool
        Setup program run, by default True.
    product : bool
        Make product files, by default True.
    main : bool
        Run main program, by default True.
    cleanup : bool
        Remove failed files, by default True.
    """

    setup: bool = True
    product: bool = True
    main: bool = True
    cleanup: bool = True

    def __init__(self, **kwargs):
        inherited = kwargs.get("temp_logger") is not None
        if not inherited:
            if "temp_logger" not in globals():
                global temp_file, temp_logger
                temp_file, temp_logger = open_temp_logger()
            temp_logger.info("Loading stage settings.")

        # Get values for each setting
        setup = StageSettings.get("setup", **kwargs)
        product = StageSettings.get("product", **kwargs)
        main = StageSettings.get("main", **kwargs)
        cleanup = StageSettings.get("cleanup", **kwargs)

        # Initialize dict to unpack
        settings = {}

        # Add each configured setting
        if setup is not None:
            settings["setup"] = setup
        if product is not None:
            settings["product"] = product
        if main is not None:
            settings["main"] = main
        if cleanup is not None:
            settings["cleanup"] = cleanup

        # Initialize instance
        super().__init__(**settings)

    def to_dict(self) -> dict[str, list[str]]:
        """Represent settings object as a dict.

        Returns
        -------
        dict[str, list[str]]
            Representation of settings object.
        """
        # Initialize dict representation
        stage_key = "stages"
        settings = {stage_key: []}

        # Add each active stage
        if self.setup:
            settings[stage_key].append("setup")
        if self.product:
            settings[stage_key].append("product")
        if self.main:
            settings[stage_key].append("main")
        if self.cleanup:
            settings[stage_key].append("cleanup")

        # Describe if all or no stages run
        if len(settings[stage_key]) == len(self.__dict__):
            settings[stage_key] = "all"
        if len(settings[stage_key]) < 1:
            settings[stage_key] = "none"

        # Return dict representation
        return settings

    @staticmethod
    def get(key: str, **kwargs) -> bool | None:
        """Get the value for a stage setting from CLI and YAML kwargs.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | None
            Setting, preferring CLI over YAML, if found.
        """
        # Get stage setting from CLI
        if f"skip_{key}" in kwargs:
            return not kwargs[f"skip_{key}"]

        # Get stage setting from YAML
        from_yaml = kwargs.get("stages")
        if from_yaml is not None:
            return (key in from_yaml) or ("all" in from_yaml)


class RemakeSettings(BaseModel):
    """Files to remake and overwrite, as flags.

    Attributes
    ----------
    products : bool
        Remake product files, by default False.
    main : bool
        Remake main files, by default False.
    """

    products: bool = False
    main: bool = False

    def __init__(self, **kwargs):
        inherited = kwargs.get("temp_logger") is not None
        if not inherited:
            if "temp_logger" not in globals():
                global temp_file, temp_logger
                temp_file, temp_logger = open_temp_logger()
            temp_logger.info("Loading remake settings.")

        # Get values for each setting
        products = RemakeSettings.get("products", **kwargs)
        main = RemakeSettings.get("main", **kwargs)

        # Initialize dict to unpack
        settings = {}

        # Add each configured setting
        if products is not None:
            settings["products"] = products
        if main is not None:
            settings["main"] = main

        # Initialize instance
        super().__init__(**settings)

    def to_dict(self) -> list[str]:
        """Represent settings object as a dict.

        Returns
        -------
        dict[str, list[str]]
            Representation of settings object.
        """
        # Initialize dict representation
        remake_key = "remake"
        settings = {remake_key: []}

        # Add each product to remake
        if self.products:
            settings[remake_key].append("products")
        if self.main:
            settings[remake_key].append("main")

        # Describe if all or no products remade
        if len(settings[remake_key]) == len(self.__dict__):
            settings[remake_key] = "all"
        if len(settings[remake_key]) < 1:
            settings[remake_key] = "none"

        # Return dict representation
        return settings

    @staticmethod
    def get(key: str, **kwargs) -> bool | None:
        """Get the value for a remake setting from CLI and YAML kwargs.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | None
            Setting, preferring CLI over YAML, if found.
        """
        # Get remake setting from CLI
        if f"remake_{key}" in kwargs:
            return kwargs[f"remake_{key}"]

        # Get remake setting from YAML
        from_yaml = kwargs.get("remake")
        if (from_yaml is not None) and ((key in from_yaml) or ("all" in from_yaml)):
            return True


class RuntimeSettings(BaseModel):
    """Local and program configurations.

    Attributes
    ----------
    date_time : datetime
        Date time at launch.
    process_id : int
        ID of process in batch, as a non-negative integer, by default 0.
    process_count : int
        Number of processes in batch, as a positive integer, by default 1.
    log_level : str
        Level at which to log, one of standard Python levels, by default info.
    progress_bar : bool
        Display progress as a loading bar, by default False.
    stages : StageSettings
        Stages to run.
    remake : RemakeSettings
        Files to remake and overwrite.
    ficls : list[FICL]
        FICLs over which to run program, by default empty.
    """

    date_time: datetime
    process_id: NonNegativeInt = 0
    process_count: PositiveInt = 1
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    progress_bar: bool = False
    stages: StageSettings
    remake: RemakeSettings
    ficls: list[FICL] = []

    def __init__(self, **kwargs):
        # Make temporary logger if not made in child class
        inherited = kwargs.get("temp_logger") is not None
        if "temp_logger" not in globals():
            global temp_file, temp_logger
        if inherited:
            temp_logger = kwargs.get("temp_logger")
        else:
            temp_file, temp_logger = open_temp_logger()
            temp_logger.info("Loading runtime settings.")

        # Initialize dict to unpack
        settings = get_settings_dict(**kwargs)

        # Get values for each primitive setting
        date_time = datetime.now()
        process_id = settings.get("process_id")
        process_count = settings.get("process_count")
        first_object = settings.get("first_object")
        last_object = settings.get("last_object")
        log_level = settings.get("log_level")
        progress_bar = settings.get("progress_bar")

        # Get values for each sub-setting
        stages = settings["stages"] if inherited else StageSettings(**settings)
        remake = settings["remake"] if inherited else RemakeSettings(**settings)

        # Initialize dict to unpack
        settings |= {"date_time": date_time, "stages": stages, "remake": remake}

        # Add each configured setting
        if process_id is not None:
            settings["process_id"] = process_id
        if process_count is not None:
            settings["process_count"] = process_count
        if log_level is not None:
            settings["log_level"] = log_level
        if progress_bar is not None:
            settings["progress_bar"] = progress_bar

        # Initialize instance
        super().__init__(**settings)

        # Validate batch settings
        if self.process_id >= self.process_count:
            raise ValueError(
                f"process ID {self.process_id} > # processes {self.process_count}"
            )

        # Get values for each model
        temp_logger.info("Loading FICLs.")

        # NOTE Child classes of this class MUST pass these kwargs to the init
        # function of its super class, for each FICL
        # Catalog path for FICL, with kw: "F_I_C_L_catalog"
        # Science path for FICL, with kw: "F_I_C_L_science"
        ficlo_settings = get_ficlo_dict(**settings)

        # Iterate over each permutation of FICL settings
        ficl_permutations = itertools.product(
            ficlo_settings["fields"],
            ficlo_settings["image_versions"],
            ficlo_settings["catalog_versions"],
            ficlo_settings["filters"],
        )
        for ficl_permutation in ficl_permutations:
            try:
                # Skip permutation if missing catalog or science path
                ficl_str = "_".join(ficl_permutation)
                if (f"{ficl_str}_catalog" not in settings) or (
                    f"{ficl_str}_science" not in settings
                ):
                    raise KeyError(f"input files missing")

                # Initialize dict to unpack
                ficl_attributes = {
                    "field": ficl_permutation[0],
                    "image_version": ficl_permutation[1],
                    "catalog_version": ficl_permutation[2],
                    "filter": ficl_permutation[3],
                    "objects": ficlo_settings["objects"],
                    "process_id": self.process_id,
                    "process_count": self.process_count,
                    "first_object": first_object,
                    "last_object": last_object,
                    "catalog": settings[f"{ficl_str}_catalog"],
                    "science": settings[f"{ficl_str}_science"],
                }

                # Add FICL if valid
                self.ficls.append(FICL(**ficl_attributes))

                temp_logger.info(f"Loaded FICL {ficl_str}.")
            except Exception as e:
                temp_logger.warning(f"Skipping FICL {ficl_str}: {e}.")

        # Remove temporary logger
        if not inherited:
            close_temp_logger(temp_file=temp_file, temp_logger=temp_logger)
        if "temp_logger" in globals():
            del temp_logger

    def to_dict(self) -> dict[str, int | str | datetime | dict | list]:
        """Represent settings object as a dict.

        Returns
        -------
        dict[str, int | str | datetime | dict | list]
            Representation of settings object.
        """
        # Initialize dict representation
        settings = {
            "started": self.date_time,
            "logging": self.log_level,
            "progress": "show" if self.progress_bar else "hide",
        }

        # Add batch mode parameters
        if self.process_count > 1:
            settings["batch mode"] = {
                "process": self.process_id + 1,
                "out of": self.process_count,
            }

        # Add stages as a list of stages ran
        if self.stages is not None:
            settings |= self.stages.to_dict()

        # Add remake flags as a list of products remade
        if self.remake is not None:
            settings |= self.remake.to_dict()

        # Add FICLs as a list of dicts
        settings["ficls"] = []
        for ficl in self.ficls:
            settings["ficls"].append(ficl.to_dict())

        # Describe if no FICLs run
        if len(settings["ficls"]) < 1:
            settings["ficls"] = "none"

        # Return dict representation
        return settings

    def to_yaml(self, path: Path):
        """Record settings.

        Parameters
        ----------
        path : Path
            Path to which to write settings.
        """
        yaml.dump(self.to_dict(), open(path, mode="a"), sort_keys=False)

    def setup_dirs(self, paths: list[Path]):
        """Make missing directories.

        Parameters
        ----------
        paths : list[Path]
            Paths to required directories.
        """
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def setup_logs(self, path: Path) -> logging.Logger:
        """Make missing loggers.

        Parameters
        ----------
        path : Path
            Path to logging file.

        Returns
        -------
        Logger
            Logging object.
        """
        return logs.setup(path=path, level=self.log_level)

    def cleanup_dirs(self, paths: list[tuple[Path, list[str]]]):
        """Remove failed directories.

        Parameters
        ----------
        paths : list[tuple[Path, list[str]]]
            Paths paired with required sub-paths, to be removed if any sub-path
            not found.
        """
        for path, required_sub_paths in paths:
            sub_paths = [sub_path.name for sub_path in path.iterdir()]

            for required_sub_path in required_sub_paths:
                if required_sub_path not in sub_paths:
                    shutil.rmtree(path, ignore_errors=True)
                    break


class ScienceSettings(BaseModel):
    """Scientific algorithm configurations.

    Attributes
    ----------
    minimum : int
        Minimum square image dimensions, in pixels, as a positive integer, by
        default 32.
    scale : float
        Multiplier on initial radius to determine image size, as a positive
        float, by default 20.0.
    """

    minimum: PositiveInt = 32
    scale: PositiveFloat = 20.0

    def __init__(self, **kwargs):
        # Make temporary logger if not made in child class
        inherited = kwargs.get("temp_logger") is not None
        if "temp_logger" not in globals():
            global temp_file, temp_logger
        if inherited:
            temp_logger = kwargs.get("temp_logger")
        else:
            temp_file, temp_logger = open_temp_logger()
            temp_logger.info("Loading science settings.")

        # Initialize dict to unpack
        settings = get_settings_dict(**kwargs)

        # Get values for each primitive setting
        minimum = ScienceSettings.get("minimum", **settings)
        scale = ScienceSettings.get("scale", **settings)

        # Add each configured setting
        if minimum is not None:
            settings["minimum"] = minimum
        if scale is not None:
            settings["scale"] = scale

        # Initialize instance
        super().__init__(**settings)

        # Remove temporary logger
        if not inherited:
            close_temp_logger(temp_file=temp_file, temp_logger=temp_logger)
        if "temp_logger" in globals():
            del temp_logger

    def to_dict(self) -> dict[str, bool | int | float | str]:
        """Represent settings object as a dict.

        Returns
        -------
        dict[str, bool | int | float | str]
            Representation of settings object.
        """
        # Initialize dict representation
        settings = {"science": {"minimum": self.minimum, "scale": self.scale}}

        # Return dict representation
        return settings

    def to_yaml(self, path: Path):
        """Record settings.

        Parameters
        ----------
        path : Path
            Path to which to write settings.
        """
        yaml.dump(self.to_dict(), open(path, mode="a"), sort_keys=False)

    @staticmethod
    def get(key: str, **kwargs) -> bool | int | float | str | None:
        """Get the value for a science setting from CLI and YAML kwargs.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | int | float | str | None
            Setting, preferring CLI over YAML, if found.
        """
        # Get science setting from CLI
        if key in kwargs:
            return kwargs[key]

        # Get science setting from YAML
        if ("science" in kwargs) and (key in kwargs["science"]):
            return kwargs["science"][key]


# Functions


def open_temp_logger() -> tuple[tempfile.NamedTemporaryFile, logging.Logger]:
    """Open a temporary logger object.

    Returns
    -------
    tuple[NamedTemporaryFile, Logger, Logger]
        Temporary file, temporary logger, and base logging object.

    Raises
    ------
    FileExistsError
        Temporary logger already created by child class.
    """
    # Open and return temporary file and logger
    temp_file = tempfile.NamedTemporaryFile()
    base_logger = logs.setup(path=temp_file.name)
    temp_logger = logging.getLogger("SETTINGS")
    return temp_file, temp_logger, base_logger


def close_temp_logger(
    temp_file: tempfile.NamedTemporaryFile,
    temp_logger: logging.Logger,
    base_logger: logging.Logger,
):
    """Close opened temporary logger object.

    Parameters
    ----------
    temp_file : NamedTemporaryFile
        Temporary file to close.
    temp_logger : Logger
        Temporary logger to close.
    base_logger : Logger
        Root logger to close.

    Raises
    ------
    FileExistsError
        Temporary logger to be closed by child class.
    """
    # Close temporary logger
    base_logger.handlers.clear()
    temp_logger.handlers.clear()
    temp_file.close()


def get_settings_dict(**kwargs) -> dict[str,]:
    """Get a dict of settings from CLI call kwargs.

    Returns
    -------
    dict[str,]
        Settings dict mapping setting keys to their values, from both CLI and
        YAML, if provided, preferring CLI.
    """
    # Initialize dict with YAML settings
    try:
        config_path = misc.get_path_object(kwargs["config"])
        settings = yaml.safe_load(open(config_path, mode="r"))
    except:
        settings = {}

    # Merge dict with non-None CLI settings, preferring CLI
    try:
        settings |= {k: v for k, v in kwargs.items() if v is not None}
    except:
        pass

    # Return settings dict
    return settings


def get_ficlo_dict(**kwargs) -> dict[str, list[str | int] | None]:
    """Get a dict of FICLO settings from CLI and YAML kwargs.

    Returns
    -------
    dict[str, list[str | int] | None]
        Settings dict mapping FICLO setting names to their values,
        preferring CLI values over YAML.

    Raises
    ------
    KeyError
        Missing any of FICL keys.
    """
    # Get single FICLO settings
    field = kwargs.get("field")
    imver = kwargs.get("image_version")
    catver = kwargs.get("catalog_version")
    filter = kwargs.get("filter")
    object = kwargs.get("object")

    # Get multiple FICLO settings
    fields = kwargs.get("fields") if field is None else [field]
    imvers = kwargs.get("image_versions") if imver is None else [imver]
    catvers = kwargs.get("catalog_versions") if catver is None else [catver]
    filters = kwargs.get("filters") if filter is None else [filter]
    objects = kwargs.get("objects") if object is None else [object]

    # Validate existence
    if fields is None:
        raise KeyError("fields missing")
    if imvers is None:
        raise KeyError("image versions missing")
    if catvers is None:
        raise KeyError("catalog versions missing")
    if filters is None:
        raise KeyError("filters missing")

    # Return as dict
    return {
        "fields": fields,
        "image_versions": imvers,
        "catalog_versions": catvers,
        "filters": filters,
        "objects": objects,
    }
